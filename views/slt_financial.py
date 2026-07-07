"""
views/slt_financial.py — Financial Pacing Dashboard.
Replaces scatter with cumulative curve + gap-to-expected bar.
"""
import streamlit as st
import pandas as pd
from data.loader import load_initiatives
from utils.pacing import enrich_dataframe
from components.financial_charts import (revenue_pacing_bar, ebitda_pacing_bar,
                                          cost_pacing_bar, ebitda_cumulative_curve,
                                          ebitda_gap_bar)
from components.ui import fmt_currency, fmt_date, metric_card
from components.filters import render_global_filter


def render():
    st.markdown("## 💰 Financial Pacing Dashboard")
    st.caption("BOD-level initiatives · financial forecasts vs realized actuals")

    df_raw = enrich_dataframe(load_initiatives())
    df     = render_global_filter(df_raw)
    bod    = df[df["category"] == "BOD"].copy()

    if bod.empty:
        st.info("No BOD-level initiatives match current filters.")
        return

    # ── Portfolio EBITDA overview ─────────────────────────────────────────
    st.markdown("### EBITDA Portfolio Pacing")

    ebitda_rows = bod[bod["forecasted_ebitda"].notna()].copy()
    if not ebitda_rows.empty:
        on_p = int((ebitda_rows["ebitda_pace_score"] >= 1.0).sum())
        at_r = int(((ebitda_rows["ebitda_pace_score"] >= 0.75) &
                    (ebitda_rows["ebitda_pace_score"] < 1.0)).sum())
        bhnd = int((ebitda_rows["ebitda_pace_score"] < 0.75).sum())
        no_d = int(ebitda_rows["ebitda_pace_score"].isna().sum())
        c1,c2,c3,c4 = st.columns(4)
        with c1: metric_card("On Pace",     str(on_p), color="#5a8010")
        with c2: metric_card("At Risk",     str(at_r), color="#d97706")
        with c3: metric_card("Behind Pace", str(bhnd), color="#dc2626")
        with c4: metric_card("No Data",     str(no_d), color="#aac4d4")

    # Cumulative curve + gap bar side by side
    cv1, cv2 = st.columns(2)
    with cv1:
        st.plotly_chart(ebitda_cumulative_curve(bod), use_container_width=True)
        st.caption("Dashed line = expected pace based on project timelines. "
                   "Solid line = actual realized to date.")
    with cv2:
        st.plotly_chart(ebitda_gap_bar(bod), use_container_width=True)
        st.caption("Each bar = Realized − Expected Today. "
                   "🔴 Red = behind pace · 🟢 Green = ahead of pace.")

    st.markdown("---")

    # ── EBITDA detail bar ─────────────────────────────────────────────────
    st.markdown("### EBITDA: Forecasted vs Realized (by Initiative)")
    st.plotly_chart(ebitda_pacing_bar(ebitda_rows if not ebitda_rows.empty else bod),
                    use_container_width=True)

    st.markdown("---")

    # ── Revenue ───────────────────────────────────────────────────────────
    st.markdown("### Revenue Pacing")
    rev_rows = bod[bod["forecasted_revenue"].notna()].copy()
    st.plotly_chart(revenue_pacing_bar(rev_rows if not rev_rows.empty else bod),
                    use_container_width=True)

    st.markdown("---")

    # ── Cost ─────────────────────────────────────────────────────────────
    st.markdown("### Project Cost Tracking")
    st.caption("🟢 Under budget · 🟡 Approaching budget · 🔴 Over budget")
    st.plotly_chart(cost_pacing_bar(bod), use_container_width=True)

    st.markdown("---")

    # ── Pacing detail table ───────────────────────────────────────────────
    st.markdown("### Pacing Detail Table")
    show_cols = ["name","sponsor","owner","status","pct_complete",
                 "forecasted_ebitda","realized_ebitda","ebitda_pace_score","ebitda_pace_label",
                 "forecasted_revenue","realized_revenue",
                 "forecasted_cost","realized_cost",
                 "target_completion","days_remaining","pct_time_elapsed"]
    show_cols = [c for c in show_cols if c in bod.columns]
    tbl = bod[show_cols].copy()
    rename = {
        "name":"Initiative","sponsor":"Sponsor","owner":"Owner","status":"Status",
        "pct_complete":"% Done",
        "forecasted_ebitda":"Fcst EBITDA","realized_ebitda":"Real EBITDA",
        "ebitda_pace_score":"Pace Score","ebitda_pace_label":"Pace",
        "forecasted_revenue":"Fcst Rev","realized_revenue":"Real Rev",
        "forecasted_cost":"Fcst Cost","realized_cost":"Real Cost",
        "target_completion":"Target","days_remaining":"Days Left","pct_time_elapsed":"% Time",
    }
    tbl.rename(columns=rename, inplace=True)
    for col in ["Fcst EBITDA","Real EBITDA","Fcst Rev","Real Rev","Fcst Cost","Real Cost"]:
        if col in tbl.columns:
            tbl[col] = tbl[col].apply(fmt_currency)
    if "% Done"  in tbl.columns: tbl["% Done"]  = tbl["% Done"].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "—")
    if "% Time"  in tbl.columns: tbl["% Time"]  = tbl["% Time"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
    if "Pace Score" in tbl.columns: tbl["Pace Score"] = tbl["Pace Score"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    if "Target"  in tbl.columns: tbl["Target"]  = tbl["Target"].apply(fmt_date)
    if "Days Left" in tbl.columns: tbl["Days Left"] = tbl["Days Left"].apply(lambda x: str(int(x)) if pd.notna(x) else "—")
    st.dataframe(tbl, use_container_width=True, hide_index=True)
