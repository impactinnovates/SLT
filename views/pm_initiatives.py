"""
pages/pm_initiatives.py — Plant Manager view: regional SM initiatives
"""
import streamlit as st
import pandas as pd
from data.loader import load_initiatives, update_initiative
from components.ui import fmt_date, fmt_currency, edit_form
from data.models import STATUS_COLORS, STATUS_ICONS


def render():
    st.markdown("## 📋 My Initiatives")
    user = st.session_state.current_user

    df  = load_initiatives()
    # PM sees only SM-category initiatives in their region/ownership
    sub = df[(df["category"] == "SM") & ((df["owner"] == user) | (df["region"].str.contains(user, na=False)))].copy()

    if sub.empty:
        # Fallback: show all SM initiatives they're involved in
        sub = df[(df["category"] == "SM") & (df["sponsor"] == user)].copy()

    if sub.empty:
        st.info("No SM-level initiatives assigned to your region. Contact your SLT sponsor to be added.")
        return

    st.caption(f"{len(sub)} initiatives in your scope")

    show_comp = st.toggle("Show Completed", value=False)
    if not show_comp:
        sub = sub[sub["status"] != "Completed"]

    for _, row in sub.sort_values(["status","name"]).iterrows():
        iid    = str(row.get("id",""))
        status = row.get("status","")
        color  = STATUS_COLORS.get(status,"#64748B")
        icon   = STATUS_ICONS.get(status,"⚪")
        pct    = row.get("pct_complete",0) or 0

        with st.expander(f"{icon} {row.get('name','')}  ·  {fmt_date(row.get('target_completion'))}", expanded=False):
            st.markdown(f"""
            <div style="height:5px;background:#1E293B;border-radius:99px;overflow:hidden;margin-bottom:10px">
              <div style="width:{pct}%;height:100%;background:{color};border-radius:99px"></div>
            </div>
            """, unsafe_allow_html=True)

            c1,c2,c3 = st.columns(3)
            c1.markdown(f"**Status:** {status}")
            c2.markdown(f"**Progress:** {pct:.0f}%")
            c3.markdown(f"**Target:** {fmt_date(row.get('target_completion'))}")

            if row.get("next_action","").strip():
                st.markdown(f"**→ Next Action:** {row.get('next_action','')}")
            if row.get("blockers","").strip():
                st.warning(f"⚠️ **Blocker:** {row.get('blockers','')}")

            # PM can update status, %, next action, blockers — no financials
            def on_save(fields, _iid=iid):
                if update_initiative(_iid, fields):
                    st.success("✅ Updated")
                    st.rerun()

            edit_form(row, user, "PM", on_save, on_delete=None)
