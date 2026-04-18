import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Rehmat POS", layout="wide")

# ================= GOOGLE SHEETS =================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("Rehmat_POS")

inventory_sheet = sheet.worksheet("Inventory")
sales_sheet = sheet.worksheet("Sales")
expenses_sheet = sheet.worksheet("Expenses")
udhar_sheet = sheet.worksheet("Udhar")   # NEW

# ================= LOAD DATA =================
def load_data():
    inventory = pd.DataFrame(inventory_sheet.get_all_records())
    sales = pd.DataFrame(sales_sheet.get_all_records())
    expenses = pd.DataFrame(expenses_sheet.get_all_records())
    udhar = pd.DataFrame(udhar_sheet.get_all_records())

    if not inventory.empty:
        inventory["quantity"] = pd.to_numeric(inventory["quantity"], errors="coerce").fillna(0)

    if not sales.empty:
        sales["profit"] = pd.to_numeric(sales["profit"], errors="coerce").fillna(0)

    if not expenses.empty:
        expenses["amount"] = pd.to_numeric(expenses["amount"], errors="coerce").fillna(0)

    if not udhar.empty:
        udhar["amount"] = pd.to_numeric(udhar["amount"], errors="coerce").fillna(0)

    return inventory, sales, expenses, udhar

inventory, sales, expenses, udhar = load_data()

# ================= HEADER =================
st.title("Rehmat Boot House POS System")

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Inventory", "Sales", "Expenses", "Udhar"])

# ================= DASHBOARD =================
if menu == "Dashboard":
    inventory, sales, expenses, udhar = load_data()

    total_profit = sales["profit"].sum() if not sales.empty else 0
    total_expense = expenses["amount"].sum() if not expenses.empty else 0

    # ===== UDHAR CALC =====
    given = udhar[udhar["type"] == "given"]["amount"].sum() if not udhar.empty else 0
    taken = udhar[udhar["type"] == "taken"]["amount"].sum() if not udhar.empty else 0
    paid = udhar[udhar["type"] == "paid"]["amount"].sum() if not udhar.empty else 0
    received = udhar[udhar["type"] == "received"]["amount"].sum() if not udhar.empty else 0

    udhar_payable = taken - paid
    udhar_receivable = given - received

    net_profit = total_profit - total_expense - udhar_payable + udhar_receivable

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Profit", f"Rs {total_profit}")
    col2.metric("Expenses", f"Rs {total_expense}")
    col3.metric("You Will Get", f"Rs {udhar_receivable}")
    col4.metric("You Will Pay", f"Rs {udhar_payable}")

    st.success(f"FINAL NET PROFIT: Rs {net_profit}")

# ================= INVENTORY =================
elif menu == "Inventory":
    st.subheader("Add Product")

    product_id = st.text_input("Product ID")
    name = st.text_input("Product Name")
    category = st.selectbox("Category", ["Men", "Women", "Kids"])
    cost_price = st.number_input("Cost Price", min_value=0.0)
    quantity = st.number_input("Quantity", min_value=0)

    if st.button("Add Product"):
        inventory_sheet.append_row([product_id, name, category, cost_price, quantity])
        st.success("Added")
        st.rerun()

    st.dataframe(pd.DataFrame(inventory_sheet.get_all_records()))

# ================= SALES =================
elif menu == "Sales":
    inventory, sales, expenses, udhar = load_data()

    if not inventory.empty:
        product = st.selectbox("Product", inventory["product_id"].astype(str))
        selected = inventory[inventory["product_id"].astype(str) == product].iloc[0]

        quantity = st.number_input("Qty", min_value=1)
        sale_price = st.number_input("Sale Price", min_value=0.0)

        payment_type = st.selectbox("Payment Type", ["Cash", "Udhar"])
        customer_name = st.text_input("Customer Name (if udhar)")

        if st.button("Record Sale"):
            if quantity > selected["quantity"]:
                st.error("Not enough stock")
            else:
                profit = (sale_price - selected["cost_price"]) * quantity
                new_qty = selected["quantity"] - quantity

                cell = inventory_sheet.find(str(product))
                inventory_sheet.update_cell(cell.row, 5, new_qty)

                sales_sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    product,
                    quantity,
                    sale_price,
                    profit
                ])

                # ===== UDHAR ENTRY =====
                if payment_type == "Udhar":
                    udhar_sheet.append_row([
                        datetime.now().strftime("%Y-%m-%d"),
                        customer_name,
                        "given",
                        sale_price * quantity,
                        "pending"
                    ])

                st.success("Sale Recorded")
                st.rerun()

# ================= EXPENSE =================
elif menu == "Expenses":
    desc = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0)

    if st.button("Add Expense"):
        expenses_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d"),
            desc,
            amount
        ])
        st.success("Added")
        st.rerun()

# ================= UDHAR =================
elif menu == "Udhar":
    st.subheader("Udhar Management")

    name = st.text_input("Name")
    amount = st.number_input("Amount", min_value=0.0)

    action = st.selectbox("Type", ["You Gave (Udhar)", "You Took", "Payment Received", "Payment Paid"])

    if st.button("Save"):
        type_map = {
            "You Gave (Udhar)": "given",
            "You Took": "taken",
            "Payment Received": "received",
            "Payment Paid": "paid"
        }

        udhar_sheet.append_row([
            datetime.now().strftime("%Y-%m-%d"),
            name,
            type_map[action],
            amount,
            "done"
        ])

        st.success("Saved")
        st.rerun()

    st.subheader("All Udhar Records")
    st.dataframe(pd.DataFrame(udhar_sheet.get_all_records()))
