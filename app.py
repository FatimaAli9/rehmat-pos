import streamlit as st
import pandas as pd
import json
import gspread
import time
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

# safe worksheet loading
try:
    inventory_sheet = sheet.worksheet("Inventory")
    sales_sheet = sheet.worksheet("Sales")
    expenses_sheet = sheet.worksheet("Expenses")
except:
    st.error("❌ Sheet tabs missing! Check names: Inventory, Sales, Expenses")
    st.stop()

# ================= LOAD DATA =================
@st.cache_data(ttl=5)
def load_data():
    inventory = pd.DataFrame(inventory_sheet.get_all_records())
    sales = pd.DataFrame(sales_sheet.get_all_records())
    expenses = pd.DataFrame(expenses_sheet.get_all_records())

    if not inventory.empty:
        inventory["quantity"] = pd.to_numeric(inventory["quantity"], errors="coerce").fillna(0)

    if not sales.empty:
        sales["profit"] = pd.to_numeric(sales["profit"], errors="coerce").fillna(0)

    if not expenses.empty:
        expenses["amount"] = pd.to_numeric(expenses["amount"], errors="coerce").fillna(0)

    return inventory, sales, expenses

inventory, sales, expenses = load_data()

# ================= HEADER =================
col1, col2 = st.columns([1, 5])

with col1:
    try:
        st.image("logo.png", width=80)
    except:
        pass

with col2:
    st.title("Rehmat Boot House POS System")

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Inventory", "Sales", "Expenses"])

# ================= DASHBOARD =================
if menu == "Dashboard":
    st.subheader("📊 Dashboard")

    inventory, sales, expenses = load_data()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Products", len(inventory))
    col2.metric("Stock", inventory["quantity"].sum() if not inventory.empty else 0)
    col3.metric("Profit", f"Rs. {sales['profit'].sum() if not sales.empty else 0}")
    col4.metric("Expenses", f"Rs. {expenses['amount'].sum() if not expenses.empty else 0}")

    # DAILY
    st.subheader("📅 Today Summary")

    today = pd.Timestamp.today().date()
    today_profit = 0
    today_exp = 0

    if not sales.empty:
        sales["date"] = pd.to_datetime(sales["date"], errors="coerce")
        today_profit = sales[sales["date"].dt.date == today]["profit"].sum()

    if not expenses.empty:
        expenses["date"] = pd.to_datetime(expenses["date"], errors="coerce")
        today_exp = expenses[expenses["date"].dt.date == today]["amount"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Today's Profit", f"Rs. {today_profit}")
    c2.metric("Today's Expense", f"Rs. {today_exp}")
    c3.metric("Net", f"Rs. {today_profit - today_exp}")

# ================= INVENTORY =================
elif menu == "Inventory":
    st.subheader("📦 Add Product")

    product_id = st.text_input("Product ID")
    name = st.text_input("Product Name")
    category = st.selectbox("Category", ["Men", "Women", "Kids"])
    cost_price = st.number_input("Cost Price", min_value=0.0)
    quantity = st.number_input("Quantity", min_value=0, step=1)

    if st.button("Add Product"):
        if product_id and name:
            time.sleep(1)
            inventory_sheet.append_row([
                product_id,
                name,
                category,
                float(cost_price),
                int(quantity)
            ])
            st.success("✅ Product Added!")
            st.cache_data.clear()
        else:
            st.error("Fill all fields")

    st.subheader("📋 Inventory")
    st.dataframe(inventory)

# ================= SALES =================
elif menu == "Sales":
    st.subheader("💰 Record Sale")

    inventory, sales, expenses = load_data()

    if inventory.empty:
        st.warning("No products available")
    else:
        st.dataframe(inventory)

        product = st.selectbox("Product ID", inventory["product_id"].astype(str))
        selected = inventory[inventory["product_id"].astype(str) == product].iloc[0]

        st.info(f"Stock: {selected['quantity']} | Cost: Rs. {selected['cost_price']}")

        quantity = st.number_input("Quantity", min_value=1, step=1)
        sale_price = st.number_input("Sale Price", min_value=0.0)

        if st.button("Record Sale"):
            if quantity > selected["quantity"]:
                st.error("Not enough stock")
            else:
                quantity = int(quantity)
                sale_price = float(sale_price)
                cost_price = float(selected["cost_price"])

                profit = (sale_price - cost_price) * quantity
                new_qty = int(selected["quantity"] - quantity)

                cell = inventory_sheet.find(str(product))
                time.sleep(1)
                inventory_sheet.update_cell(cell.row, 5, str(new_qty))

                time.sleep(1)
                sales_sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    product,
                    quantity,
                    sale_price,
                    profit
                ])

                st.success(f"Sale Done | Profit Rs. {profit}")
                st.cache_data.clear()

    st.subheader("📊 Sales History")
    st.dataframe(pd.DataFrame(sales_sheet.get_all_records()))

# ================= EXPENSES =================
elif menu == "Expenses":
    st.subheader("💸 Add Expense")

    desc = st.text_input("Description")
    amount = st.number_input("Amount", min_value=0.0)

    if st.button("Add Expense"):
        if desc and amount > 0:
            time.sleep(1)
            expenses_sheet.append_row([
                datetime.now().strftime("%Y-%m-%d"),
                desc,
                float(amount)
            ])
            st.success("Expense Added")
            st.cache_data.clear()
        else:
            st.error("Enter valid data")

    st.subheader("📋 Expense History")
    st.dataframe(pd.DataFrame(expenses_sheet.get_all_records()))
