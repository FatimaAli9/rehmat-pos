import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Rehmat POS PRO", layout="wide")

# ================= GOOGLE CONNECT =================
@st.cache_resource
def connect():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

client = connect()

# ================= OPEN / CREATE SHEET =================
try:
    sheet = client.open("Rehmat_POS")
except:
    sheet = client.create("Rehmat_POS")

def get_or_create_sheet(name, headers):
    try:
        ws = sheet.worksheet(name)
        data = ws.get_all_values()

        if len(data) == 0:
            ws.append_row(headers)
        elif data[0] != headers:
            ws.clear()
            ws.append_row(headers)

        return ws
    except:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="20")
        ws.append_row(headers)
        return ws

# ================= INIT SHEETS =================
inventory_sheet = get_or_create_sheet(
    "Inventory",
    ["product_id","name","category","cost_price","quantity"]
)

sales_sheet = get_or_create_sheet(
    "Sales",
    ["date","product_id","quantity","sale_price","profit"]
)

expenses_sheet = get_or_create_sheet(
    "Expenses",
    ["date","description","amount"]
)

udhar_sheet = get_or_create_sheet(
    "Udhar",
    ["date","name","type","amount","status"]
)

# ================= LOAD DATA =================
@st.cache_data(ttl=3)
def load_data():
    def read(ws, cols):
        try:
            df = pd.DataFrame(ws.get_all_records())
            if df.empty:
                return pd.DataFrame(columns=cols)
            return df
        except:
            return pd.DataFrame(columns=cols)

    inventory = read(inventory_sheet, ["product_id","name","category","cost_price","quantity"])
    sales = read(sales_sheet, ["date","product_id","quantity","sale_price","profit"])
    expenses = read(expenses_sheet, ["date","description","amount"])
    udhar = read(udhar_sheet, ["date","name","type","amount","status"])

    for df, col in [(inventory,"quantity"), (sales,"profit"),
                    (expenses,"amount"), (udhar,"amount")]:
        if not df.empty and col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return inventory, sales, expenses, udhar

# ================= UI =================
col1, col2 = st.columns([1, 5])

with col1:
    try:
        st.image("logo.png", width=80)
    except:
        pass

with col2:
    st.title("Rehmat Boot House POS System")

menu = st.sidebar.selectbox("Menu", ["Dashboard","Inventory","Sales","Expenses","Loan"])

inventory, sales, expenses, udhar = load_data()

# ================= DASHBOARD =================
if menu == "Dashboard":
    total_profit = sales["profit"].sum()
    total_expense = expenses["amount"].sum()

    given = udhar[udhar["type"]=="given"]["amount"].sum()
    taken = udhar[udhar["type"]=="taken"]["amount"].sum()
    paid = udhar[udhar["type"]=="paid"]["amount"].sum()
    received = udhar[udhar["type"]=="received"]["amount"].sum()

    payable = taken - paid
    receivable = given - received

    net = total_profit - total_expense - payable + receivable

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Profit", f"Rs {int(total_profit)}")
    c2.metric("Expenses", f"Rs {int(total_expense)}")
    c3.metric("You Will Get", f"Rs {int(receivable)}")
    c4.metric("You Will Pay", f"Rs {int(payable)}")

    st.success(f"NET PROFIT: Rs {int(net)}")

# ================= INVENTORY =================
elif menu == "Inventory":
    st.subheader("Add Product")

    with st.form("inventory_form", clear_on_submit=True):
        pid = st.text_input("Product ID")
        name = st.text_input("Name")
        cat = st.selectbox("Category", ["Men","Women","Kids"])
        cost = st.number_input("Cost", min_value=0.0)
        qty = st.number_input("Quantity", min_value=0)

        submitted = st.form_submit_button("Add Product")

        if submitted:
            if pid and name:
                inventory_sheet.append_row([pid,name,cat,float(cost),int(qty)])
                st.success("Added")
                st.cache_data.clear()
                st.rerun()

    st.dataframe(inventory)

# ================= SALES =================
elif menu == "Sales":

    # ===== TODAY SUMMARY =====
    st.subheader("📊 Today's Sales Summary")

    today = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))

    if not sales.empty:
        sales["date"] = pd.to_datetime(sales["date"], errors="coerce")
        today_sales = sales[sales["date"].dt.date == today.date()].copy()

        total_revenue = (today_sales["sale_price"] * today_sales["quantity"]).sum()
        total_profit = today_sales["profit"].sum()
        total_items = today_sales["quantity"].sum()
    else:
        today_sales = pd.DataFrame()
        total_revenue = total_profit = total_items = 0

    c1,c2,c3 = st.columns(3)
    c1.metric("Today's Sales", f"Rs {int(total_revenue)}")
    c2.metric("Today's Profit", f"Rs {int(total_profit)}")
    c3.metric("Items Sold", int(total_items))

    # ===== TABLE =====
    st.subheader("📋 Today's Sales Details")

    if not today_sales.empty:
        today_sales["revenue"] = today_sales["sale_price"] * today_sales["quantity"]
        today_sales = today_sales.sort_values(by="date", ascending=False)

        st.dataframe(
            today_sales[["date","product_id","quantity","sale_price","revenue","profit"]],
            use_container_width=True
        )
    else:
        st.info("No sales today")

    # ===== SELL FORM =====
    st.subheader("💰 Record Sale")

    if not inventory.empty:
        with st.form("sales_form", clear_on_submit=True):

            product = st.selectbox("Product", inventory["product_id"].astype(str))
            selected = inventory[inventory["product_id"].astype(str)==product].iloc[0]

            st.info(f"Stock: {int(selected['quantity'])}")

            qty = st.number_input("Qty", min_value=1)
            price = st.number_input("Sale Price", min_value=0.0)

            pay_type = st.selectbox("Payment", ["Cash","Udhar"])
            customer = st.text_input("Customer Name")

            submitted = st.form_submit_button("Sell")

            if submitted:
                if qty > selected["quantity"]:
                    st.error("Not enough stock")
                else:
                    profit = (price - selected["cost_price"]) * qty
                    new_qty = int(selected["quantity"] - qty)

                    row_index = inventory[inventory["product_id"].astype(str)==product].index[0] + 2
                    inventory_sheet.update(f"E{row_index}", [[int(new_qty)]])

                    sales_sheet.append_row([
                        datetime.now().strftime("%Y-%m-%d"),
                        product,
                        int(qty),
                        float(price),
                        float(profit)
                    ])

                    if pay_type == "Udhar":
                        udhar_sheet.append_row([
                            datetime.now().strftime("%Y-%m-%d"),
                            customer,
                            "given",
                            float(price*qty),
                            "pending"
                        ])

                    st.success("Sale Done")
                    st.cache_data.clear()
                    st.rerun()

# ================= EXPENSE =================
elif menu == "Expenses":
    with st.form("expense_form", clear_on_submit=True):
        desc = st.text_input("Description")
        amt = st.number_input("Amount", min_value=0.0)

        submitted = st.form_submit_button("Add Expense")

        if submitted:
            if desc:
                expenses_sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    desc,
                    float(amt)
                ])
                st.success("Added")
                st.cache_data.clear()
                st.rerun()

    st.dataframe(expenses)

# ================= UDHAR =================
elif menu == "Loan":
    st.subheader("Loan Ledger System")

    # ================= LOAD PENDING =================
    pending_udhar = udhar[udhar["status"] == "pending"]

    # ================= UPDATE EXISTING UDHAR =================
    st.subheader("Update Loan Status")

    if not pending_udhar.empty:

        selected_index = st.selectbox(
            "Select Pending Loan",
            pending_udhar.index,
            format_func=lambda i: f"{pending_udhar.loc[i,'name']} | Rs {pending_udhar.loc[i,'amount']} | {pending_udhar.loc[i,'type']}"
        )

        new_status = st.selectbox("Mark As", ["paid", "received"])

        if st.button("Update Status"):
            try:
                row_number = int(selected_index) + 2  # sheet row mapping

                # update ONLY status column (5th column)
                udhar_sheet.update_cell(row_number, 5, new_status)

                st.success("Loan updated successfully ✅")
                st.cache_data.clear()
                st.rerun()

            except Exception as e:
                st.error(f"Error updating udhar: {e}")

    else:
        st.info("No pending loan 🎉")

    st.divider()

    # ================= ADD NEW UDHAR =================
    st.subheader("Add New Loan")

    with st.form("udhar_form", clear_on_submit=True):
        name = st.text_input("Customer Name")
        amount = st.number_input("Amount", min_value=0.0)
        udhar_type = st.selectbox("Type", ["given", "taken"])

        submitted = st.form_submit_button("Save Loan")

        if submitted:
            if name:
                udhar_sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    name,
                    udhar_type,
                    float(amount),
                    "pending"
                ])

                st.success("Loan added successfully")
                st.cache_data.clear()
                st.rerun()

    st.divider()

    # ================= FULL TABLE =================
    st.subheader("All Loan Records")
    st.dataframe(udhar, use_container_width=True)
