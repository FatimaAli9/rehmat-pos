import streamlit as st
import pandas as pd
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Rehmat POS", layout="wide")

# ---- Google Sheets Connection ----
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("Rehmat_POS")

inventory_sheet = sheet.worksheet("Inventory")
sales_sheet = sheet.worksheet("Sales")

# ---- Load Data ----
def load_data():
    inventory = pd.DataFrame(inventory_sheet.get_all_records())
    sales = pd.DataFrame(sales_sheet.get_all_records())
    return inventory, sales

inventory, sales = load_data()

col1, col2 = st.columns([1, 5])

with col1:
    st.image("logo.png", width=80)

with col2:
    st.title("Rehmat Boot House POS System")

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Inventory", "Sales"])

# ================= DASHBOARD =================
if menu == "Dashboard":
    st.subheader("📊 Dashboard")

    inventory, sales = load_data()

    total_products = len(inventory)
    total_stock = inventory["quantity"].sum() if not inventory.empty else 0
    total_profit = sales["profit"].sum() if not sales.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Products", total_products)
    col2.metric("Total Stock", total_stock)
    col3.metric("Total Profit", f"Rs. {total_profit}")

    # ---- Low Stock Alert ----
    st.subheader("🚨 Low Stock Products")
    if not inventory.empty:
        low_stock = inventory[inventory["quantity"] < 5]
        if not low_stock.empty:
            st.dataframe(low_stock)
        else:
            st.success("All products have sufficient stock!")

    # ---- Sales Chart ----
    if not sales.empty:
        st.subheader("📈 Daily Profit Trend")
        sales["date"] = pd.to_datetime(sales["date"])
        daily_profit = sales.groupby("date")["profit"].sum().reset_index()

        fig = px.line(daily_profit, x="date", y="profit", title="Daily Profit")
        st.plotly_chart(fig, use_container_width=True)

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
            inventory_sheet.append_row([product_id, name, category, cost_price, quantity])
            st.success("✅ Product Added!")
            st.rerun()
        else:
            st.error("Please fill all fields")

    st.subheader("🔍 Filter Inventory")

    category_filter = st.selectbox("Filter by Category", ["All", "Men", "Women", "Kids"])

    if not inventory.empty:
        if category_filter != "All":
            filtered_inventory = inventory[inventory["category"] == category_filter]
        else:
            filtered_inventory = inventory

        st.dataframe(filtered_inventory)

# ================= SALES =================
elif menu == "Sales":
    st.subheader("💰 Record Sale")

    inventory, sales = load_data()

    if inventory.empty:
        st.warning("No products available")
    else:
        st.write("### Available Products")
        st.dataframe(inventory)

        st.write("### ➕ Add Sale")

        product = st.selectbox("Select Product ID", inventory["product_id"].astype(str))
        selected_product = inventory[inventory["product_id"].astype(str) == product].iloc[0]

        st.info(f"Stock: {selected_product['quantity']} | Cost Price: Rs. {selected_product['cost_price']}")

        quantity = st.number_input("Quantity Sold", min_value=1, step=1)
        sale_price = st.number_input("Selling Price", min_value=0.0)

        if st.button("Record Sale"):
            if quantity > selected_product["quantity"]:
                st.error("❌ Not enough stock!")
            else:
                cost_price = selected_product["cost_price"]
                profit = (sale_price - cost_price) * quantity

                # Update stock
                new_qty = selected_product["quantity"] - quantity
                cell = inventory_sheet.find(str(product))
                inventory_sheet.update_cell(cell.row, 5, new_qty)

                # Save sale
                sales_sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d"),
                    product,
                    quantity,
                    sale_price,
                    profit
                ])

                st.success(f"✅ Sale recorded! Profit: Rs. {profit}")
                st.rerun()

    # ---- Sales History ----
    st.subheader("📊 Sales History")
    sales = pd.DataFrame(sales_sheet.get_all_records())
    st.dataframe(sales)

    # ---- Daily Summary ----
    st.subheader("📅 Today's Summary")

    if not sales.empty:
        sales["date"] = pd.to_datetime(sales["date"])
        today = pd.Timestamp.today().date()

        today_sales = sales[sales["date"].dt.date == today]

        st.metric("Today's Profit", f"Rs. {today_sales['profit'].sum()}")
        st.metric("Items Sold", today_sales["quantity"].sum())
