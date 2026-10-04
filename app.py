import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text

st.set_page_config(page_title="My Spends", page_icon="💸", layout="centered")

# --- DATABASE SETUP (PostgreSQL via Supabase) ---
conn = st.connection("postgresql", type="sql")

with conn.session as s:
    s.execute(text('''CREATE TABLE IF NOT EXISTS spends (id SERIAL PRIMARY KEY, date DATE, category TEXT, amount REAL, notes TEXT)'''))
    s.execute(text('''CREATE TABLE IF NOT EXISTS settings (key TEXT UNIQUE, value REAL)'''))
    s.commit()

limit_df = conn.query("SELECT value FROM settings WHERE key='weekly_limit'", ttl=0)
WEEKLY_LIMIT = limit_df.iloc[0]['value'] if not limit_df.empty else 4000.0

# --- INITIALIZE SESSION STATE ---
if 'input_amt' not in st.session_state: st.session_state.input_amt = 0.0
if 'input_cat' not in st.session_state: st.session_state.input_cat = "Other"
if 'input_note' not in st.session_state: st.session_state.input_note = ""
if 'input_date' not in st.session_state: st.session_state.input_date = datetime.today()

def apply_quick_log(amt, cat, note):
    st.session_state.input_amt = float(amt)
    st.session_state.input_cat = cat
    st.session_state.input_note = note

def save_spend():
    if st.session_state.input_amt > 0:
        with conn.session as s:
            s.execute(
                text("INSERT INTO spends (date, category, amount, notes) VALUES (:date, :category, :amount, :notes)"),
                {"date": st.session_state.input_date.strftime('%Y-%m-%d'), 
                 "category": st.session_state.input_cat, 
                 "amount": st.session_state.input_amt, 
                 "notes": st.session_state.input_note}
            )
            s.commit()
        st.session_state.input_amt = 0.0
        st.session_state.input_note = ""
        st.session_state.input_date = datetime.today()

# --- LOAD DATA ---
df = conn.query("SELECT * FROM spends", ttl=0)
df['date'] = pd.to_datetime(df['date'], errors='coerce')
today = pd.to_datetime("today").normalize()

# --- TIME CALCULATIONS ---
start_of_week = today - timedelta(days=today.weekday())
current_month_start = today.replace(day=1)
last_month_end = current_month_start - timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

this_week_spend = df[df['date'] >= start_of_week]['amount'].sum() if not df.empty else 0
this_month_spend = df[df['date'] >= current_month_start]['amount'].sum() if not df.empty else 0
last_month_spend = df[(df['date'] >= last_month_start) & (df['date'] <= last_month_end)]['amount'].sum() if not df.empty else 0

# --- HEADER & PROGRESS UI ---
st.markdown("<h2 style='text-align: center;'>💸 Spends Tracker</h2>", unsafe_allow_html=True)

with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    col1.metric("Spent This Week", f"₹{this_week_spend:,.0f}")
    
    if last_month_spend > 0:
        delta_val = this_month_spend - last_month_spend
        col2.metric("Spent This Month", f"₹{this_month_spend:,.0f}", delta=f"₹{delta_val:,.0f} vs last mth", delta_color="inverse")
    else:
        col2.metric("Spent This Month", f"₹{this_month_spend:,.0f}")
        
    col3.metric("Weekly Limit", f"₹{WEEKLY_LIMIT:,.0f}")
    
    progress = min(this_week_spend / WEEKLY_LIMIT, 1.0) if WEEKLY_LIMIT > 0 else 0.0
    st.progress(progress)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["➕ Add", "📊 Analytics", "⚙️ Manage"])

with tab1:
    st.caption("Tap to auto-fill, then click Save Spend:")
    qc1, qc2, qc3 = st.columns(3)
    qc1.button("☕ ₹50 Chai", on_click=apply_quick_log, args=(50, "Food Delivery", "Snack"), use_container_width=True)
    qc2.button("🛵 ₹80 Ride", on_click=apply_quick_log, args=(80, "Commute", "Rapido"), use_container_width=True)
    qc3.button("🛒 ₹200 Mart", on_click=apply_quick_log, args=(200, "Groceries", "Blinkit/BigBasket"), use_container_width=True)

    st.divider()

    st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.2f", key="input_amt")
    st.selectbox("Category", [
        "Commute", "Groceries", "Food Delivery", 
        "Dining Out", "Shopping", "Bills", "Other"
    ], key="input_cat")
    st.text_input("Notes (Optional)", key="input_note")
    st.date_input("Date", key="input_date")
    
    st.button("Save Spend", type="primary", use_container_width=True, on_click=save_spend)

with tab2:
    if not df.empty:
        st.subheader("🏆 Key Highlights")
        hc1, hc2 = st.columns(2)
        hc3, hc4 = st.columns(2)
        
        hc1.metric("Total All-Time Spend", f"₹{df['amount'].sum():,.0f}")
        
        yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')
        y_df = df[df['date'].dt.strftime('%Y-%m-%d') == yesterday_str]
        if not y_df.empty:
            y_max = y_df.loc[y_df['amount'].idxmax()]
            hc2.metric("Yesterday's Highest", f"₹{y_max['amount']:,.0f}", f"{y_max['category']} - {y_max['notes']}", delta_color="off")
        else:
            hc2.metric("Yesterday's Highest", "₹0", "No spends")
            
        w_df = df[df['date'] >= start_of_week]
        if not w_df.empty:
            w_max = w_df.loc[w_df['amount'].idxmax()]
            hc3.metric("This Week's Highest", f"₹{w_max['amount']:,.0f}", f"{w_max['category']} - {w_max['notes']}", delta_color="off")
        else:
            hc3.metric("This Week's Highest", "₹0", "No spends")
            
        m_df = df[df['date'] >= current_month_start]
        if not m_df.empty:
            m_max = m_df.loc[m_df['amount'].idxmax()]
            hc4.metric("This Month's Highest", f"₹{m_max['amount']:,.0f}", f"{m_max['category']} - {m_max['notes']}", delta_color="off")
        else:
            hc4.metric("This Month's Highest", "₹0", "No spends")

        st.divider()

        st.subheader("📈 14-Day Trend")
        fourteen_days_ago = today - timedelta(days=13)
        date_range = pd.date_range(start=fourteen_days_ago, end=today)
        
        trend_df = df[df['date'] >= fourteen_days_ago]
        if not trend_df.empty:
            daily_totals = trend_df.groupby('date')['amount'].sum()
        else:
            daily_totals = pd.Series(dtype=float)
            
        daily_totals = daily_totals.reindex(date_range, fill_value=0)
        daily_totals.index = daily_totals.index.strftime('%d %b')
        st.line_chart(daily_totals)
        
        st.divider()

        st.subheader("Top Categories (All Time)")
        cat_totals = df.groupby('category')['amount'].sum().reset_index().set_index('category')
        st.bar_chart(cat_totals)
        
        st.subheader("Recent Spends")
        display_df = df.sort_values(by='date', ascending=False).drop(columns=['id']).head(15)
        display_df['date'] = display_df['date'].dt.strftime('%d %b')
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No data yet.")

with tab3:
    st.subheader("App Settings")
    new_limit = st.number_input("Set Custom Weekly Limit (₹)", min_value=100.0, value=float(WEEKLY_LIMIT), step=500.0)
    if st.button("Update Limit", use_container_width=True):
        with conn.session as s:
            s.execute(text("INSERT INTO settings (key, value) VALUES ('weekly_limit', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"), {"val": new_limit})
            s.commit()
        st.success("Weekly limit updated!")
        st.rerun()
        
    st.divider()
    
    st.subheader("Delete a Record")
    if not df.empty:
        recent_records = conn.query("SELECT id, date, category, amount, notes FROM spends ORDER BY date DESC, id DESC LIMIT 20", ttl=0)
        record_dict = {}
        for _, row in recent_records.iterrows():
            label = f"{row['date']} | {row['category']} | ₹{row['amount']} ({row['notes']})"
            record_dict[label] = row['id']
            
        selected_label = st.selectbox("Select a recent spend to remove:", list(record_dict.keys()))
        
        if st.button("Delete Selected Spend", use_container_width=True):
            with conn.session as s:
                s.execute(text("DELETE FROM spends WHERE id = :id"), {"id": record_dict[selected_label]})
                s.commit()
            st.success("Record deleted successfully!")
            st.rerun()
    else:
        st.info("No records to delete.")
