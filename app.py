import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Rehmat POS PRO", layout="wide")

# ================= GOOGLE SHEETS =================
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
sheet = client.open("Rehmat_POS")

inventory_sheet = sheet.worksheet("Inventory")
sales_sheet = sheet.worksheet("Sales")
expenses_sheet = sheet.worksheet("Expenses")
udhar_sheet = sheet.worksheet("Udhar")

# ================= LOAD DATA =================
@st.cache_data(ttl=5)
def load_data():
    inventory = pd.DataFrame(inventory_sheet.get_all_records())
    sales = pd.DataFrame(sales_sheet.get_all_records())
    expenses = pd.DataFrame(expenses_sheet.get_all_records())
    udhar = pd.DataFrame(udhar_sheet.get_all_records())

    for df, col in [(inventory, "quantity"), (sales, "profit"),
                    (expenses, "amount"), (udhar, "amount")]:
        if not df.empty:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return inventory, sales, expenses, udhar

inventory, sales, expenses, udhar = load_data()

# ================= HEADER =================
st.title("Rehmat Boot House POS PRO")

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Inventory", "Sales", "Expenses", "Udhar"])

# ================= DASHBOARD =================
if menu == "Dashboard":
    inventory, sales, expenses, udhar = load_data()

    total_profit = sales["profit"].sum() if not sales.empty else 0
    total_expense = expenses["amount"].sum() if not expenses.empty else 0

    given = udhar[udhar["type"] == "given"]["amount"].sum() if not udhar.empty else 0
    taken = udhar[udhar["type"] == "taken"]["amount"].sum() if not udhar.empty else 0
    paid = udhar[udhar["type"] == "paid"]["amount"].sum() if not udhar.empty else 0
    received = udhar[udhar["type"] == "received"]["amount"].sum() if not udhar.empty else 0

    payable = taken - paid
    receivable = given - received

    net = total_profit - total_expense - payable + receivable

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Profit", f"Rs {int(total_profit)}")
    c2.metric("Expenses", f"Rs {int(total_expense)}")
    c3.metric("You Will Get", f"Rs {int(receivable)}")
    c4.metric("You Will Pay", f"Rs {int(payable)}")

    st.success(f"NET PROFIT: Rs {int(net)}")

# ================= INVENTORY =================
elif menu == "Inventory":
    st.subheader("Add Product")

    pid = st.text_input("Product ID")
    name = st.text_input("Name")
    cat = st.selectbox("Category", ["Men", "Women", "Kids"])
    cost = st.number_input("Cost", min_value=0.0)
    qty = st.number_input("Quantity", min_value=0)

    if st.button("Add"):
        inventory_sheet.append_row([pid, name, cat, float(cost), int(qty)])
        st.success("Added")
        st.cache_data.clear()
        st.rerun()

    st.dataframe(inventory)

# ================= SALES =================
elif menu == "Sales":
    inventory, sales, expenses, udhar = load_data()

    if inventory.empty:
        st.warning("No products")
    else:
        product = st.selectbox("Product", inventory["product_id"].astype(str))
        selected = inventory[inventory["product_id"].astype(str) == product].iloc[0]

        st.info(f"Stock: {int(selected['quantity'])}")

        qty = st.number_input("Qty", min_value=1)
        price = st.number_input("Sale Price", min_value=0.0)

        pay_type = st.selectbox("Payment", ["Cash", "Udhar"])
        customer = st.text_input("Customer Name")

        if st.button("Sell"):
            if qty > selected["quantity"]:
                st.error("Not enough stock")
            else:
                profit = (price - selected["cost_price"]) * qty
                new_qty = int(selected["quantity"] - qty)

                # ==== SAFE ROW INDEX ====
                row_index = inventory[inventory["product_id"].astype(str) == str(product)].index[0] + 2

                # ==== BATCH UPDATE ====
                inventory_sheet.update(f"E{row_index}", [[new_qty]])

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
                        float(price * qty),
                        "pending"
                    ])

                st.success("Done")
                st.cache_data.clear()
                st.rerun()

# ================= EXPENSE =================
elif menu == "Expenses":
    desc = st.text_input("Desc")
    amt = st.number_input("Amount", min_value=0.0)

    if st.button("Add"):
        expenses_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d"),
            desc,
            float(amt)
        ])
        st.success("Added")
        st.cache_data.clear()
        st.rerun()

# ================= UDHAR =================
elif menu == "Udhar":
    st.subheader("Udhar Ledger")

    name = st.text_input("Name")
    amt = st.number_input("Amount", min_value=0.0)

    action = st.selectbox("Type", ["Given", "Taken", "Received", "Paid"])

    if st.button("Save"):
        udhar_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d"),
            name,
            action.lower(),
            float(amt),
            "done"
        ])
        st.success("Saved")
        st.cache_data.clear()
        st.rerun()

    st.dataframe(udhar)
