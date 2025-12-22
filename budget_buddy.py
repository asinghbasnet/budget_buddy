import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from pathlib import Path
import re

# Page config
st.set_page_config(page_title="Budget Buddy", page_icon="💰", layout="wide")

st.markdown("""
<style>
    h1, h2, h3 { color: #1E40AF; }
    .section-title {
        background: #3B82F6;
        color: white;
        padding: 10px 14px;
        border-radius: 10px;
        font-weight: 800;
        letter-spacing: 0.4px;
        margin-top: 18px;
        margin-bottom: 10px;
    }
    .subtle {
        color: #64748B;
        font-size: 0.95rem;
        margin-top: -6px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

def section_header(title: str, subtitle: str = None):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='subtle'>{subtitle}</div>", unsafe_allow_html=True)

# Storage
DATA_DIR = Path("budget_data")
DATA_DIR.mkdir(exist_ok=True)

def get_data_file(month_ym: str) -> Path:
    return DATA_DIR / f"budget_{month_ym}.json"

def default_month_data() -> dict:
    return {
        "rollover": 0.0,
        "debt": 0.0,
        "income_items": [{"name": "Paycheck", "amount": 0.0}],
        "bill_items": [
            {"name": "Rent/Mortgage", "amount": 0.0, "paid": False},
            {"name": "Utilities", "amount": 0.0, "paid": False},
            {"name": "Internet", "amount": 0.0, "paid": False},
        ],
        "expense_items": [
            {"name": "Groceries", "spent": 0.0},
            {"name": "Dining Out", "spent": 0.0},
            {"name": "Transportation", "spent": 0.0},
        ],
        "savings_items": [
            {"name": "Emergency Fund", "saved": 0.0},
            {"name": "Retirement", "saved": 0.0},
        ],
    }

def load_month_data(month_ym: str) -> dict:
    fp = get_data_file(month_ym)
    if fp.exists():
        with open(fp, "r") as f:
            d = json.load(f)
        # Normalize old data
        out = default_month_data()
        out["rollover"] = float(d.get("rollover", 0.0) or 0.0)
        out["debt"] = float(d.get("debt", 0.0) or 0.0)
        
        # Income
        income = d.get("income_items", [])
        out["income_items"] = [{"name": x.get("name", ""), "amount": float(x.get("amount", 0.0) or 0.0)} for x in income]
        
        # Bills - just amount and paid
        bills = d.get("bill_items", [])
        out["bill_items"] = [
            {
                "name": x.get("name", ""),
                "amount": float(x.get("amount") or x.get("actual", 0.0) or 0.0),
                "paid": bool(x.get("paid", False))
            } for x in bills
        ]
        
        # Expenses - just spent
        expenses = d.get("expense_items", [])
        out["expense_items"] = [{"name": x.get("name", ""), "spent": float(x.get("spent", 0.0) or 0.0)} for x in expenses]
        
        # Savings - just saved
        savings = d.get("savings_items", [])
        out["savings_items"] = [{"name": x.get("name", ""), "saved": float(x.get("saved", 0.0) or 0.0)} for x in savings]
        
        return out
    return default_month_data()

def save_month_data(month_ym: str, data: dict):
    fp = get_data_file(month_ym)
    with open(fp, "w") as f:
        json.dump(data, f, indent=2)

def list_saved_months() -> list[str]:
    months = []
    for p in DATA_DIR.glob("budget_*.json"):
        m = re.findall(r"budget_(\d{4}-\d{2})\.json", p.name)
        if m:
            months.append(m[0])
    return sorted(set(months))

def aggregate_year(year: int) -> pd.DataFrame:
    months = [m for m in list_saved_months() if m.startswith(f"{year}-")]
    rows = []
    for ym in months:
        d = load_month_data(ym)
        income = sum(float(x.get("amount", 0.0) or 0.0) for x in d.get("income_items", []))
        expenses = sum(float(x.get("spent", 0.0) or 0.0) for x in d.get("expense_items", []))
        bills = sum(float(x.get("amount", 0.0) or 0.0) for x in d.get("bill_items", []))
        saved = sum(float(x.get("saved", 0.0) or 0.0) for x in d.get("savings_items", []))
        debt = float(d.get("debt", 0.0) or 0.0)
        left = income - expenses - bills - saved - debt
        rows.append({
            "Month": ym,
            "Income": income,
            "Expenses": expenses,
            "Bills": bills,
            "Saved": saved,
            "Debt": debt,
            "Left": left,
        })
    return pd.DataFrame(rows)

# Session state
if "current_month" not in st.session_state:
    st.session_state.current_month = datetime.now().strftime("%Y-%m")

# Header
st.title("💰 Budget Buddy - Expense Tracker")

col1, col2, col3, col4 = st.columns([2.1, 1.6, 1.5, 0.8])

with col1:
    selected_month_dt = st.date_input(
        "Budget Period",
        value=datetime.strptime(st.session_state.current_month + "-01", "%Y-%m-%d"),
    )
    new_month = selected_month_dt.strftime("%Y-%m")
    if new_month != st.session_state.current_month:
        st.session_state.current_month = new_month
        st.rerun()

with col2:
    st.markdown(f"### 📅 {selected_month_dt.strftime('%B %Y')}")

with col3:
    view_mode = st.radio("View", ["Month", "Year"], horizontal=True, index=0)

with col4:
    st.markdown("### 💵 USD")

# Helpful note
if view_mode == "Month":
    st.info("💡 **Tip:** Enter your transactions in the sections below, then click **💾 Save** to update the charts above!")

st.divider()

# Load data
data = load_month_data(st.session_state.current_month)

# Year view setup
saved_months = list_saved_months()
current_year = int(st.session_state.current_month.split("-")[0])
available_years = sorted({int(m.split("-")[0]) for m in saved_months} | {current_year})

year_df = None
selected_year = None
if view_mode == "Year":
    y1, y2 = st.columns([1.3, 2.7])
    with y1:
        selected_year = st.selectbox("Year", available_years, index=available_years.index(current_year))
    year_df = aggregate_year(selected_year)
    
    y_income = float(year_df["Income"].sum()) if not year_df.empty else 0.0
    y_expenses = float(year_df["Expenses"].sum()) if not year_df.empty else 0.0
    y_bills = float(year_df["Bills"].sum()) if not year_df.empty else 0.0
    y_saved = float(year_df["Saved"].sum()) if not year_df.empty else 0.0
    y_debt = float(year_df["Debt"].sum()) if not year_df.empty else 0.0
    y_left = y_income - y_expenses - y_bills - y_saved - y_debt

# Helper function to calculate totals
def calculate_totals(data):
    total_income = sum(float(x.get("amount", 0.0) or 0.0) for x in data.get("income_items", []))
    total_bills = sum(float(x.get("amount", 0.0) or 0.0) for x in data.get("bill_items", []))
    total_expenses = sum(float(x.get("spent", 0.0) or 0.0) for x in data.get("expense_items", []))
    total_savings = sum(float(x.get("saved", 0.0) or 0.0) for x in data.get("savings_items", []))
    total_debt = float(data.get("debt", 0.0) or 0.0)
    rollover = float(data.get("rollover", 0.0) or 0.0)
    left_amount = total_income + rollover - total_expenses - total_bills - total_savings - total_debt
    return total_income, total_bills, total_expenses, total_savings, total_debt, rollover, left_amount

# VISUAL OVERVIEW
section_header("📊 VISUAL OVERVIEW", "See where your money goes")

# Recalculate totals to show latest data
total_income, total_bills, total_expenses, total_savings, total_debt, rollover, left_amount = calculate_totals(data)

if view_mode == "Month":
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### Spending Breakdown")
        if total_income > 0 and (total_expenses + total_bills + total_savings) > 0:
            allocation = pd.DataFrame({
                "Category": ["Expenses", "Bills", "Savings"],
                "Amount": [total_expenses, total_bills, total_savings],
            })
            allocation = allocation[allocation["Amount"] > 0]
            fig = px.pie(allocation, values="Amount", names="Category")
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add transactions to see spending breakdown")
    
    with c2:
        st.markdown("### Amount Left")
        base = max(total_income + rollover, 0.0)
        remaining = max(left_amount, 0.0)
        spent = max(base - remaining, 0.0)
        
        fig = go.Figure(data=[go.Pie(
            values=[remaining, spent] if base > 0 else [1],
            labels=["Remaining", "Spent"] if base > 0 else ["No Data"],
            hole=0.65,
        )])
        fig.update_layout(
            annotations=[dict(text=f"${left_amount:,.2f}", x=0.5, y=0.5, font_size=26, showarrow=False)],
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    
    if left_amount < 0:
        st.error(f"⚠️ You spent ${abs(left_amount):,.2f} more than you earned")
    
    st.markdown("### Cash Flow")
    cf = pd.DataFrame({
        "Category": ["Income", "Expenses", "Bills", "Savings", "Debt"],
        "Amount": [total_income, total_expenses, total_bills, total_savings, total_debt],
    })
    fig = px.bar(cf, x="Category", y="Amount")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.markdown(f"### Year Summary ({selected_year})")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Income", f"${y_income:,.2f}")
    k2.metric("Expenses", f"${y_expenses:,.2f}")
    k3.metric("Saved", f"${y_saved:,.2f}")
    k4.metric("Left", f"${y_left:,.2f}")
    
    if year_df is not None and not year_df.empty:
        year_df = year_df.copy()
        year_df["MonthLabel"] = year_df["Month"].apply(
            lambda x: datetime.strptime(x + "-01", "%Y-%m-%d").strftime("%b")
        )
        
        ych1, ych2 = st.columns(2)
        with ych1:
            st.markdown("### Monthly Expenses")
            fig = px.bar(year_df, x="MonthLabel", y="Expenses")
            st.plotly_chart(fig, use_container_width=True)
        
        with ych2:
            st.markdown("### Monthly Savings")
            fig = px.bar(year_df, x="MonthLabel", y="Saved")
            st.plotly_chart(fig, use_container_width=True)

st.divider()

# FINANCIAL OVERVIEW
section_header("📈 FINANCIAL OVERVIEW", "Summary of your finances")

# Recalculate totals again
total_income, total_bills, total_expenses, total_savings, total_debt, rollover, left_amount = calculate_totals(data)

if view_mode == "Month":
    ov1, ov2 = st.columns([3, 1])
    with ov1:
        overview_df = pd.DataFrame({
            "Category": [
                "+ Rollover",
                "+ Income",
                "- Expenses",
                "- Bills",
                "- Savings",
                "- Debt",
                "LEFT",
            ],
            "Amount": [
                rollover,
                total_income,
                total_expenses,
                total_bills,
                total_savings,
                total_debt,
                left_amount,
            ],
        })
        st.dataframe(
            overview_df.style.format({"Amount": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )
    
    with ov2:
        st.markdown("**Adjustments**")
        data["rollover"] = float(st.number_input("Rollover", value=float(data["rollover"]), step=10.0, format="%.2f"))
        data["debt"] = float(st.number_input("Debt Payment", value=float(data["debt"]), step=10.0, format="%.2f"))

else:
    if year_df is not None and not year_df.empty:
        year_overview = pd.DataFrame({
            "Category": ["Income", "Expenses", "Bills", "Saved", "Debt", "LEFT"],
            "Amount": [y_income, y_expenses, y_bills, y_saved, y_debt, y_left],
        })
        st.dataframe(
            year_overview.style.format({"Amount": "${:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )

st.divider()

if view_mode == "Month":
    # INCOME
    section_header("💵 INCOME", "Track your income sources")
    
    income_df = pd.DataFrame(data["income_items"])
    edited_income = st.data_editor(
        income_df,
        column_config={
            "name": st.column_config.TextColumn("Source", required=True),
            "amount": st.column_config.NumberColumn("Amount ($)", format="%.2f", min_value=0.0),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="income_editor",
    )
    data["income_items"] = edited_income.to_dict("records")
    st.markdown(f"### **Total Income: ${sum(float(x.get('amount', 0.0) or 0.0) for x in data['income_items']):,.2f}**")
    
    st.divider()
    
    # BILLS
    section_header("📄 BILLS", "Track your bills")
    
    bill_df = pd.DataFrame(data["bill_items"])
    edited_bills = st.data_editor(
        bill_df,
        column_config={
            "name": st.column_config.TextColumn("Bill Name", required=True),
            "amount": st.column_config.NumberColumn("Amount ($)", format="%.2f", min_value=0.0),
            "paid": st.column_config.CheckboxColumn("Paid", default=False),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="bills_editor",
    )
    data["bill_items"] = edited_bills.to_dict("records")
    
    paid_count = sum(1 for x in data["bill_items"] if x.get("paid", False))
    st.markdown(f"**Total Bills: ${sum(float(x.get('amount', 0.0) or 0.0) for x in data['bill_items']):,.2f}** | ✅ Paid: {paid_count}/{len(data['bill_items'])}")
    
    st.divider()
    
    # EXPENSES
    section_header("💳 EXPENSES", "Track your spending")
    
    expense_df = pd.DataFrame(data["expense_items"])
    edited_expenses = st.data_editor(
        expense_df,
        column_config={
            "name": st.column_config.TextColumn("Category", required=True),
            "spent": st.column_config.NumberColumn("Spent ($)", format="%.2f", min_value=0.0),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="expenses_editor",
    )
    
    data["expense_items"] = edited_expenses.to_dict("records")
    st.markdown(f"**Total Expenses: ${sum(float(x.get('spent', 0.0) or 0.0) for x in data['expense_items']):,.2f}**")
    
    st.divider()
    
    # SAVINGS
    section_header("🏦 SAVINGS", "Track money saved")
    
    savings_df = pd.DataFrame(data["savings_items"])
    edited_savings = st.data_editor(
        savings_df,
        column_config={
            "name": st.column_config.TextColumn("Savings Account", required=True),
            "saved": st.column_config.NumberColumn("Saved ($)", format="%.2f", min_value=0.0),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="savings_editor",
    )
    
    data["savings_items"] = edited_savings.to_dict("records")
    st.markdown(f"**Total Saved: ${sum(float(x.get('saved', 0.0) or 0.0) for x in data['savings_items']):,.2f}**")
    
    st.divider()
    
    # ACTIONS
    section_header("✅ ACTIONS", "Save or export your data")
    
    a1, a2, a3 = st.columns([2, 1, 1])
    
    with a1:
        if st.button("💾 Save", type="primary", use_container_width=True):
            save_month_data(st.session_state.current_month, data)
            st.success(f"✅ Saved for {selected_month_dt.strftime('%B %Y')}!")
            st.rerun()  # Refresh to update charts
    
    with a2:
        if st.button("📥 Export CSV", use_container_width=True):
            export_rows = []
            for item in data.get("income_items", []):
                export_rows.append({"Category": "Income", "Item": item.get("name", ""), "Amount": float(item.get("amount", 0.0) or 0.0)})
            for item in data.get("bill_items", []):
                export_rows.append({"Category": "Bills", "Item": item.get("name", ""), "Amount": float(item.get("amount", 0.0) or 0.0)})
            for item in data.get("expense_items", []):
                export_rows.append({"Category": "Expenses", "Item": item.get("name", ""), "Amount": float(item.get("spent", 0.0) or 0.0)})
            for item in data.get("savings_items", []):
                export_rows.append({"Category": "Savings", "Item": item.get("name", ""), "Amount": float(item.get("saved", 0.0) or 0.0)})
            
            export_df = pd.DataFrame(export_rows)
            csv = export_df.to_csv(index=False)
            
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"expenses_{st.session_state.current_month}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    
    with a3:
        if st.button("🔄 Reset", use_container_width=True):
            fp = get_data_file(st.session_state.current_month)
            if fp.exists():
                fp.unlink()
            st.success("Reset! Reloading...")
            st.rerun()

# Auto-save on any change
save_month_data(st.session_state.current_month, data)

# Footer
st.divider()
st.markdown(
    "<div style='text-align:center;color:#64748B;padding:14px;'>💰 Budget Buddy - Simple Expense Tracker</div>",
    unsafe_allow_html=True,
)
