"""
pages/slt_new.py — Create new SLT initiative
"""
import streamlit as st
from datetime import date
from data.loader import create_initiative
from data.models import parse_currency


def render():
    st.markdown("## ➕ New Initiative")
    user = st.session_state.current_user

    with st.form("new_initiative"):
        name = st.text_input("Initiative Name *")
        desc = st.text_area("Description", height=100)

        c1, c2, c3 = st.columns(3)
        category  = c1.selectbox("Category", ["BOD","SM"])
        priority  = c2.selectbox("Priority", ["1","2","3"], format_func=lambda x: {"1":"P1 — Critical","2":"P2 — High","3":"P3 — Standard"}[x])
        status    = c3.selectbox("Status", ["Not Started","On Track","At Risk","Behind","Blocked"])

        c4, c5, c6 = st.columns(3)
        sponsor = c4.text_input("Sponsor", value=user)
        owner   = c5.text_input("Owner")
        region  = c6.selectbox("Region", ["All Facilities","Elgin, IL","Jonesboro, AR","Lake Mills","Clare, MI","Midland","Pasadena, TX","East Stroudsburg","Olympic","IEG Service","UK"])

        c7, c8 = st.columns(2)
        start_dt  = c7.date_input("Start Date",  value=date.today())
        target_dt = c8.date_input("Target Completion")

        st.markdown("**Financial Forecasts** *(optional)*")
        ff1, ff2, ff3 = st.columns(3)
        fcst_rev    = ff1.text_input("Forecasted Revenue")
        fcst_ebitda = ff2.text_input("Forecasted EBITDA")
        fcst_cost   = ff3.text_input("Forecasted Cost")

        next_action = st.text_area("Next Action", height=60)

        submitted = st.form_submit_button("Create Initiative", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Initiative Name is required.")
            return
        fields = {
            "name":               name.strip(),
            "description":        desc,
            "category":           category,
            "priority":           priority,
            "status":             status,
            "sponsor":            sponsor,
            "owner":              owner,
            "region":             region,
            "start_date":         str(start_dt),
            "target_completion":  str(target_dt),
            "pct_complete":       0,
            "next_action":        next_action,
            "forecasted_revenue": parse_currency(fcst_rev),
            "forecasted_ebitda":  parse_currency(fcst_ebitda),
            "forecasted_cost":    parse_currency(fcst_cost),
            "created_by":         user,
            "last_updated_by":    user,
        }
        if create_initiative(fields):
            st.success(f"✅ '{name}' created successfully.")
            st.balloons()
        else:
            st.error("Failed to create initiative. Check connection settings.")
