
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, date, timedelta

# Optional dependency for PDF export
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

st.set_page_config(page_title="Universal Budget Dashboard", layout="wide")

# ---------- Session State ----------
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Month","Date","Category","Type","Budget (€)","Actual (€)","Section"])
if "categories" not in st.session_state:
    st.session_state.categories = pd.DataFrame({
        "Category": ["Salary","Other Income","Rent","Insurance","Phone","Debts",
                     "Phone Subs (ChatGPT, Google Cloud, Apple Music, Extra)",
                     "Clothing","Restaurant & Food Delivery","Bet","Trade","Groceries","Transport","Utilities","Entertainment","Miscellaneous"],
        "Type": ["Income","Income","Expense","Expense","Expense","Expense","Expense","Expense","Expense","Expense","Expense","Expense","Expense","Expense","Expense","Expense"],
        "Section": ["Savings","Savings","Needs","Needs","Needs","Needs","Wants","Wants","Wants","Wants","Wants","Needs","Needs","Needs","Wants","Wants"]
    })
if "budgets" not in st.session_state:
    st.session_state.budgets = pd.DataFrame({"Category": st.session_state.categories["Category"], "Monthly Budget (€)": [0]*len(st.session_state.categories)})
if "settings" not in st.session_state:
    st.session_state.settings = {
        "default_month": datetime.now().strftime("%Y-%m"),
        "near_budget_threshold": 10,
        "savings_goal": 300,
        "savings_rate_goal": 20,
        "no_spend_goal": 8,
        "paydays": [],          # e.g., [5,20]
        "max_loss_limit_trade": 0,  # €
        "max_loss_limit_bet": 0,    # €
        "hard_caps": {},        # {category: cap€}
    }

# ---------- Helpers ----------
def ensure_columns(df):
    cols = ["Month","Date","Category","Type","Budget (€)","Actual (€)","Section"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    # Coerce
    df["Month"] = df["Month"].fillna(st.session_state.settings["default_month"]).astype(str).str.slice(0,7)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Category"] = df["Category"].astype(str)
    df["Type"] = df["Type"].str.title()
    for c in ["Budget (€)","Actual (€)"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    # Section from categories map if missing
    cat_map = st.session_state.categories.set_index("Category")["Section"].to_dict()
    df["Section"] = df.apply(lambda r: cat_map.get(r["Category"], r.get("Section","")), axis=1)
    return df

def aggregate_monthly(df):
    m = df.assign(
        Income=df.apply(lambda r: r["Actual (€)"] if r["Type"]=="Income" else 0, axis=1),
        Expense=df.apply(lambda r: r["Actual (€)"] if r["Type"]=="Expense" else 0, axis=1)
    ).groupby("Month", as_index=False)[["Income","Expense"]].sum().sort_values("Month")
    m["Savings"] = m["Income"] - m["Expense"]
    return m

def fig_to_png_bytes(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

def current_month_key(df):
    if df.empty:
        return st.session_state.settings["default_month"]
    return df["Month"].iloc[-1]

# ---------- Navigation ----------
st.title("🏠 Universal Budget Dashboard")
tabs = st.tabs(["Home", "Budget & Entries", "Analytics", "Reports", "Settings"])

# ---------- HOME TAB ----------
with tabs[0]:
    st.header("Welcome")
    st.write("Start here: add your categories and first entries. Upload CSV/XLSX if you already have data.")

    # Categories editor
    with st.expander("➕ Add or edit categories"):
        st.caption("Map categories to Type (Income/Expense) and Section (Needs/Wants/Savings for 50/30/20).")
        st.dataframe(st.session_state.categories, use_container_width=True)
        uploaded_cats = st.file_uploader("Upload categories CSV (Category, Type, Section)", type=["csv"], key="cat_up")
        if uploaded_cats:
            newcats = pd.read_csv(uploaded_cats)
            newcats.columns = [c.strip() for c in newcats.columns]
            if {"Category","Type","Section"}.issubset(newcats.columns):
                st.session_state.categories = newcats
                st.success("Categories updated.")

    # Budgets editor
    with st.expander("💶 Set monthly budgets per category"):
        merged = pd.merge(st.session_state.categories[["Category"]], st.session_state.budgets, on="Category", how="left")
        merged["Monthly Budget (€)"] = merged["Monthly Budget (€)"].fillna(0)
        st.session_state.budgets = merged
        st.dataframe(st.session_state.budgets, use_container_width=True)

    # Quick entry form
    st.subheader("Quick Entry")
    with st.form("quick_entry"):
        left, right = st.columns(2)
        with left:
            entry_date = st.date_input("Date", value=date.today())
            entry_month = st.text_input("Month (YYYY-MM)", value=st.session_state.settings["default_month"])
            entry_category = st.selectbox("Category", options=st.session_state.categories["Category"].tolist())
            entry_type = st.selectbox("Type", options=["Income","Expense"], index=1 if entry_category not in ["Salary","Other Income"] else 0)
            entry_amount_actual = st.number_input("Actual (€)", min_value=0.0, value=0.0, step=10.0)
        with right:
            cat_budget = st.session_state.budgets.set_index("Category")["Monthly Budget (€)"].to_dict()
            suggested = float(cat_budget.get(entry_category, 0))
            entry_amount_budget = st.number_input("Budget (€) for this category", min_value=0.0, value=suggested, step=10.0)
            entry_section = st.selectbox("Section (50/30/20)", options=["Needs","Wants","Savings"], index=["Needs","Wants","Savings"].index(
                st.session_state.categories.set_index("Category").loc[entry_category,"Section"]
            ))
        submitted = st.form_submit_button("Add Entry")
        if submitted:
            new_row = pd.DataFrame([{
                "Month": str(entry_month)[:7],
                "Date": pd.to_datetime(entry_date),
                "Category": entry_category,
                "Type": entry_type,
                "Budget (€)": entry_amount_budget,
                "Actual (€)": entry_amount_actual,
                "Section": entry_section
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
            st.success("Entry added.")

    st.markdown("---")
    st.subheader("Import / Export")
    c1, c2 = st.columns(2)
    with c1:
        uploaded = st.file_uploader("Upload CSV/XLSX data", type=["csv","xlsx"], key="data_up")
        if uploaded:
            if uploaded.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
            df = ensure_columns(df)
            st.session_state.data = pd.concat([st.session_state.data, df], ignore_index=True)
            st.success(f"Imported {len(df)} rows.")
    with c2:
        st.download_button("Download current data (CSV)",
                           st.session_state.data.to_csv(index=False).encode("utf-8"),
                           "budget_data.csv", "text/csv")

# ---------- BUDGET & ENTRIES TAB ----------
with tabs[1]:
    st.header("Budget & Entries")
    data = ensure_columns(st.session_state.data.copy())
    if data.empty:
        st.info("No data yet. Add entries in Home.")
    else:
        st.dataframe(data.sort_values(["Month","Date"], na_position="last"), use_container_width=True)

        cm = current_month_key(data)
        dfm = data[data["Month"]==cm].copy()
        month_income = dfm.loc[dfm["Type"]=="Income","Actual (€)"].sum()
        month_expenses = dfm.loc[dfm["Type"]=="Expense","Actual (€)"].sum()
        month_savings = month_income - month_expenses
        month_savings_rate = (month_savings / month_income * 100) if month_income>0 else 0

        k1,k2,k3,k4 = st.columns(4)
        k1.metric("💵 Income", f"{month_income:,.0f}€")
        k2.metric("💸 Expenses", f"{month_expenses:,.0f}€")
        k3.metric("💰 Savings", f"{month_savings:,.0f}€")
        k4.metric("📈 Savings Rate", f"{month_savings_rate:.1f}%")

        bmap = st.session_state.budgets.set_index("Category")["Monthly Budget (€)"].to_dict()
        dfm["Budget (€)"] = dfm["Category"].map(bmap).fillna(dfm["Budget (€)"])
        cat_sum = dfm.groupby(["Category","Type","Section"], as_index=False)[["Budget (€)","Actual (€)"]].sum()
        cat_sum["Variance (€)"] = cat_sum["Budget (€)"] - cat_sum["Actual (€)"]
        cat_sum.loc[cat_sum["Type"]=="Income", ["Budget (€)","Variance (€)"]] = 0
        st.subheader(f"Categories — {cm}")
        st.dataframe(cat_sum.sort_values(["Type","Category"]), use_container_width=True)

# ---------- ANALYTICS TAB ----------
with tabs[2]:
    st.header("Analytics")
    data = ensure_columns(st.session_state.data.copy())
    if data.empty:
        st.info("No data yet.")
    else:
        monthly = aggregate_monthly(data)

        st.subheader("📆 Monthly Trend (Income, Expenses, Savings)")
        if not monthly.empty:
            fig1, ax1 = plt.subplots()
            ax1.plot(monthly["Month"], monthly["Income"], label="Income")
            ax1.plot(monthly["Month"], monthly["Expense"], label="Expenses")
            ax1.plot(monthly["Month"], monthly["Savings"], label="Savings")
            ax1.set_xlabel("Month")
            ax1.set_ylabel("€")
            ax1.legend()
            plt.xticks(rotation=45)
            st.pyplot(fig1)

        st.subheader("📐 50/30/20 View (Needs/Wants/Savings) — current month")
        cm = current_month_key(data)
        dfm = data[data["Month"]==cm].copy()
        month_income = dfm.loc[dfm["Type"]=="Income","Actual (€)"].sum()
        by_sec = dfm[dfm["Type"]=="Expense"].groupby("Section", as_index=False)["Actual (€)"].sum()
        needs = float(by_sec.loc[by_sec["Section"]=="Needs","Actual (€)"].sum())
        wants = float(by_sec.loc[by_sec["Section"]=="Wants","Actual (€)"].sum())
        savings = max(0.0, month_income - (needs + wants))
        st.write(f"Income: {month_income:,.0f}€ | Needs: {needs:,.0f}€ | Wants: {wants:,.0f}€ | Savings: {savings:,.0f}€")
        fig2, ax2 = plt.subplots()
        ax2.bar(["Needs","Wants","Savings"], [needs, wants, savings])
        ax2.set_ylabel("€")
        st.pyplot(fig2)

        st.subheader("⚠️ Variance by Category (Budget - Actual) — current month")
        bmap = st.session_state.budgets.set_index("Category")["Monthly Budget (€)"].to_dict()
        dfm["Budget (€)"] = dfm["Category"].map(bmap).fillna(dfm["Budget (€)"])
        exp_only = dfm[dfm["Type"]=="Expense"].groupby("Category", as_index=False)[["Budget (€)","Actual (€)"]].sum()
        exp_only["Variance (€)"] = exp_only["Budget (€)"] - exp_only["Actual (€)"]
        exp_sorted = exp_only.sort_values("Variance (€)")
        fig3, ax3 = plt.subplots()
        ax3.barh(exp_sorted["Category"], exp_sorted["Variance (€)"])
        ax3.axvline(0, linewidth=1)
        ax3.set_xlabel("€")
        st.pyplot(fig3)

        st.subheader("📈 3-Month Rolling Average (Food, Clothing)")
        keycats = ["Restaurant & Food Delivery","Clothing"]
        dfk = data[(data["Type"]=="Expense") & (data["Category"].isin(keycats))].copy()
        if not dfk.empty:
            roll = dfk.groupby(["Month","Category"], as_index=False)["Actual (€)"].sum()
            roll["Month"] = pd.to_datetime(roll["Month"] + "-01")
            roll = roll.sort_values(["Category","Month"])
            roll["Roll3"] = roll.groupby("Category")["Actual (€)"].rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
            fig4, ax4 = plt.subplots()
            for cat in keycats:
                sub = roll[roll["Category"]==cat]
                ax4.plot(sub["Month"].dt.strftime("%Y-%m"), sub["Actual (€)"], label=f"{cat} Actual")
                ax4.plot(sub["Month"].dt.strftime("%Y-%m"), sub["Roll3"], label=f"{cat} 3M Avg")
            ax4.set_xlabel("Month")
            ax4.set_ylabel("€")
            ax4.legend()
            plt.xticks(rotation=45)
            st.pyplot(fig4)
        else:
            st.info("Add data for target categories to see rolling averages.")

        st.subheader("🗓️ Weekly Pace Tracker — current month")
        year, mon = map(int, cm.split("-"))
        start = datetime(year, mon, 1)
        end = datetime(year+1, 1, 1) if mon==12 else datetime(year, mon+1, 1)
        days_in_month = (end - start).days
        today_in_month = min((datetime.now() - start).days + 1, days_in_month)
        monthly_budget_total = exp_only["Budget (€)"].sum() if not exp_only.empty else 0
        spent_to_date = exp_only["Actual (€)"].sum() if not exp_only.empty else 0
        expected_spend_to_date = monthly_budget_total * (today_in_month / days_in_month) if days_in_month else 0
        st.write(f"Budget: {monthly_budget_total:,.0f}€ | Spent to date: {spent_to_date:,.0f}€ | Expected by today: {expected_spend_to_date:,.0f}€")
        fig5, ax5 = plt.subplots()
        ax5.bar(["Spent to date","Expected by today"], [spent_to_date, expected_spend_to_date])
        ax5.set_ylabel("€")
        st.pyplot(fig5)

        st.subheader("🚧 Guardrails & Caps")
        alerts = []
        if monthly_budget_total > 0 and today_in_month < 20 and spent_to_date > 0.8 * monthly_budget_total:
            alerts.append("Overall spending has reached 80% of the monthly budget before the 20th. Slow down now.")
        caps = st.session_state.settings["hard_caps"]
        if caps:
            for cat, cap in caps.items():
                spent_cat = exp_only.loc[exp_only["Category"]==cat, "Actual (€)"].sum()
                if spent_cat > cap:
                    alerts.append(f"Category '{cat}' exceeded its hard cap of {cap:,.0f}€. Consider a spending freeze.")
        for a in alerts:
            st.warning(a)
        if not alerts:
            st.success("No guardrail breaches detected.")

        st.subheader("🎯 Risk Guards")
        for risk_cat, key in [("Trade","max_loss_limit_trade"), ("Bet","max_loss_limit_bet")]:
            limit = st.session_state.settings.get(key, 0)
            spent_cat = dfm[(dfm["Type"]=="Expense") & (dfm["Category"]==risk_cat)]["Actual (€)"].sum()
            if limit and spent_cat > limit:
                st.error(f"{risk_cat}: Loss limit of {limit:,.0f}€ exceeded. Pause activity.")

# ---------- REPORTS TAB ----------
with tabs[3]:
    st.header("Reports")
    data = ensure_columns(st.session_state.data.copy())
    if data.empty:
        st.info("No data yet.")
    else:
        monthly = aggregate_monthly(data)
        if not monthly.empty:
            fig_trend, ax_trend = plt.subplots()
            ax_trend.plot(monthly["Month"], monthly["Income"], label="Income")
            ax_trend.plot(monthly["Month"], monthly["Expense"], label="Expenses")
            ax_trend.plot(monthly["Month"], monthly["Savings"], label="Savings")
            ax_trend.set_xlabel("Month")
            ax_trend.set_ylabel("€")
            ax_trend.legend()
            plt.xticks(rotation=45)
            st.pyplot(fig_trend)

        cm = current_month_key(data)
        dfm = data[data["Month"]==cm].copy()
        bmap = st.session_state.budgets.set_index("Category")["Monthly Budget (€)"].to_dict()
        dfm["Budget (€)"] = dfm["Category"].map(bmap).fillna(dfm["Budget (€)"])
        exp_only = dfm[dfm["Type"]=="Expense"].groupby("Category", as_index=False)[["Budget (€)","Actual (€)"]].sum()
        exp_only["Variance (€)"] = exp_only["Budget (€)"] - exp_only["Actual (€)"]
        fig_var, ax_var = plt.subplots()
        exp_sorted = exp_only.sort_values("Variance (€)")
        ax_var.barh(exp_sorted["Category"], exp_sorted["Variance (€)"])
        ax_var.axvline(0, linewidth=1)
        ax_var.set_xlabel("€")
        st.pyplot(fig_var)

        fig_pie, ax_pie = plt.subplots()
        if not exp_only.empty:
            ax_pie.pie(exp_only["Actual (€)"], labels=exp_only["Category"], autopct="%1.1f%%", startangle=90)
        ax_pie.axis("equal")
        st.pyplot(fig_pie)

        month_income = dfm.loc[dfm["Type"]=="Income","Actual (€)"].sum()
        month_expenses = dfm.loc[dfm["Type"]=="Expense","Actual (€)"].sum()
        month_savings = month_income - month_expenses
        month_savings_rate = (month_savings / month_income * 100) if month_income>0 else 0
        overs = exp_only[exp_only["Variance (€)"]<0].sort_values("Variance (€)").head(5)

        st.subheader("PDF Export")
        if not REPORTLAB_OK:
            st.warning("Install reportlab to enable PDF export: `pip install reportlab`")
        else:
            trend_png = fig_to_png_bytes(fig_trend) if 'fig_trend' in locals() else None
            var_png = fig_to_png_bytes(fig_var)
            pie_png = fig_to_png_bytes(fig_pie)
            if st.button("Generate Monthly PDF"):
                buf = BytesIO()
                c = canvas.Canvas(buf, pagesize=A4)
                width, height = A4

                c.setFont("Helvetica-Bold", 16)
                c.drawString(2*cm, height-2*cm, f"Budget Report — {cm}")

                c.setFont("Helvetica", 10)
                kpi = f"Income: {month_income:,.0f}€   Expenses: {month_expenses:,.0f}€   Savings: {month_savings:,.0f}€ ({month_savings_rate:.1f}%)"
                c.drawString(2*cm, height-3*cm, kpi)

                y = height - 4*cm
                chart_w = width - 4*cm
                chart_h = 6*cm
                if trend_png:
                    c.drawImage(ImageReader(BytesIO(trend_png)), 2*cm, y-chart_h, width=chart_w, height=chart_h, preserveAspectRatio=True, mask='auto')
                    y -= (chart_h + 1*cm)
                c.drawImage(ImageReader(BytesIO(var_png)), 2*cm, y-chart_h, width=chart_w, height=chart_h, preserveAspectRatio=True, mask='auto')
                y -= (chart_h + 1*cm)
                c.drawImage(ImageReader(BytesIO(pie_png)), 2*cm, y-chart_h, width=chart_w, height=chart_h, preserveAspectRatio=True, mask='auto')

                c.showPage()
                c.setFont("Helvetica-Bold", 14)
                c.drawString(2*cm, height-2*cm, "Recommendations")
                c.setFont("Helvetica", 11)
                text = []
                goal_gap = st.session_state.settings.get("savings_goal",0) - month_savings
                if goal_gap > 0:
                    text.append(f"Increase savings by {goal_gap:,.0f}€ to hit the monthly goal.")
                for _, row in overs.iterrows():
                    text.append(f"Reduce {row['Category']} by {-row['Variance (€)']:,.0f}€ to meet budget.")
                subs_rows = exp_only[exp_only["Category"].str.contains("Subs", case=False, na=False)]
                if not subs_rows.empty:
                    text.append(f"Subscriptions total {subs_rows['Actual (€)'].sum():,.0f}€. Cancel/pause one for 60 days.")
                tx = c.beginText(2*cm, height-3*cm)
                for line in text if text else ["No immediate risks. Keep your plan."]:
                    tx.textLine(f"- {line}")
                c.drawText(tx)

                c.save()
                pdf = buf.getvalue()
                buf.close()
                st.download_button("Download PDF", data=pdf, file_name=f"Budget_Report_{cm}.pdf", mime="application/pdf")

# ---------- SETTINGS TAB ----------
with tabs[4]:
    st.header("Settings")
    s = st.session_state.settings
    s["default_month"] = st.text_input("Default Month (YYYY-MM)", value=s["default_month"])
    s["near_budget_threshold"] = st.slider("Near-budget threshold (%)", 5, 30, s["near_budget_threshold"], 1)
    colA, colB = st.columns(2)
    with colA:
        s["savings_goal"] = st.number_input("Monthly savings goal (€)", min_value=0, value=int(s["savings_goal"]), step=50)
        s["savings_rate_goal"] = st.slider("Savings rate goal (%)", 5, 50, int(s["savings_rate_goal"]), 1)
    with colB:
        s["no_spend_goal"] = st.number_input("No-spend days goal", min_value=0, value=int(s["no_spend_goal"]), step=1)
        paydays_str = st.text_input("Paydays (comma-separated days, e.g., 5,20)", value=",".join(map(str, s.get("paydays",[]))))
        try:
            s["paydays"] = [int(x.strip()) for x in paydays_str.split(",") if x.strip()]
        except:
            st.warning("Invalid paydays format. Use numbers like 5,20")
    st.markdown("**Hard Caps (category: cap€)**")
    cap_rows = []
    for cat in st.session_state.categories["Category"].tolist():
        cap_val = s["hard_caps"].get(cat, 0)
        cap_rows.append({"Category": cat, "Cap (€)": cap_val})
    caps_df = pd.DataFrame(cap_rows)
    caps_edit = st.data_editor(caps_df, num_rows="dynamic", use_container_width=True)
    s["hard_caps"] = {row["Category"]: float(row["Cap (€)"]) for _, row in caps_edit.iterrows() if float(row.get("Cap (€)",0))>0}

    st.markdown("**Risk Limits**")
    r1, r2 = st.columns(2)
    with r1:
        s["max_loss_limit_trade"] = st.number_input("Max loss limit for Trade (€)", min_value=0, value=int(s.get("max_loss_limit_trade",0)), step=50)
    with r2:
        s["max_loss_limit_bet"] = st.number_input("Max loss limit for Bet (€)", min_value=0, value=int(s.get("max_loss_limit_bet",0)), step=50)

    st.success("Settings saved in session.")
