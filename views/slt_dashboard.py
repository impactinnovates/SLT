"""
views/slt_dashboard.py  —  SLT Dashboard with expandable Needs Attention cards.
"""
import streamlit as st
import pandas as pd
from data.loader import load_initiatives, update_initiative, delete_initiative
from utils.pacing import enrich_dataframe, summary_stats
from components.ui import metric_card, fmt_currency, fmt_date, edit_form
from components.financial_charts import status_donut, ebitda_pacing_bar, revenue_pacing_bar, cost_pacing_bar
from components.filters import render_global_filter
from config.settings import is_sponsor

STATUS_COLORS = {
    "On Track":"#5a8010","At Risk":"#d97706","Behind":"#dc2626",
    "Blocked":"#7c3aed","Completed":"#0369a1","Not Started":"#aac4d4",
}
STATUS_ICONS  = {
    "On Track":"🟢","At Risk":"🟡","Behind":"🔴",
    "Blocked":"🟣","Completed":"✅","Not Started":"⚪",
}
# Severity sort: most urgent first
STATUS_SEV = {"Behind":0,"Blocked":1,"At Risk":2,"Not Started":3,"On Track":4,"Completed":5}


def _attainment_badge(realized, forecasted, label):
    """Colored % attainment pill for financial metrics."""
    try:
        if not forecasted or float(forecasted) == 0: return ""
        pct = float(realized or 0) / float(forecasted) * 100
        color = "#5a8010" if pct>=75 else "#d97706" if pct>=50 else "#dc2626"
        return (f'<span style="background:{color}18;color:{color};padding:2px 9px;'
                f'border-radius:99px;font-size:11px;font-weight:700;border:1px solid {color}44">'
                f'{label} {pct:.0f}%</span>')
    except: return ""


def render():
    st.markdown("## 📊 SLT Dashboard")
    st.caption("BOD-level strategic initiatives · Refreshed every 2 minutes")

    df_raw = load_initiatives()
    df_all = enrich_dataframe(df_raw)
    df     = render_global_filter(df_all)
    bod    = df[df["category"] == "BOD"].copy()
    stats  = summary_stats(df)
    user   = st.session_state.current_user

    # ── Status KPIs ──────────────────────────────────────────────────────
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    with k1: metric_card("Total Initiatives", str(stats["total"]),     color="#294c60")
    with k2: metric_card("On Track",          str(stats["on_track"]),  color="#5a8010")
    with k3: metric_card("At Risk",           str(stats["at_risk"]),   color="#d97706")
    with k4: metric_card("Behind",            str(stats["behind"]),    color="#dc2626")
    with k5: metric_card("Blocked",           str(stats["blocked"]),   color="#7c3aed")
    with k6: metric_card("Completed",         str(stats["completed"]), color="#0369a1")

    st.markdown("---")

    # ── Financial KPIs ─────────────────────────────────────────────────────
    st.markdown("### 💰 Financial Summary")
    f1,f2,f3,f4 = st.columns(4)
    rev_pct    = stats["rev_pct"]
    ebitda_pct = stats["ebitda_pct"]
    with f1: metric_card("Forecasted Revenue",  fmt_currency(stats["total_forecasted_rev"]),
                          f"{fmt_currency(stats['total_realized_rev'])} realized", color="#294c60")
    with f2: metric_card("Revenue Realized",    f"{rev_pct:.1f}%",
                          fmt_currency(stats["total_realized_rev"]),
                          color="#5a8010" if rev_pct>=75 else "#d97706" if rev_pct>=50 else "#dc2626")
    with f3: metric_card("Forecasted EBITDA",   fmt_currency(stats["total_forecasted_ebitda"]),
                          f"{fmt_currency(stats['total_realized_ebitda'])} realized", color="#294c60")
    with f4: metric_card("EBITDA Realized",     f"{ebitda_pct:.1f}%",
                          fmt_currency(stats["total_realized_ebitda"]),
                          color="#5a8010" if ebitda_pct>=75 else "#d97706" if ebitda_pct>=50 else "#dc2626")

    st.markdown("---")

    # ── Charts ──────────────────────────────────────────────────────────────
    ch1, ch2 = st.columns([1,2])
    with ch1: st.plotly_chart(status_donut(bod), use_container_width=True)
    with ch2: st.plotly_chart(ebitda_pacing_bar(bod), use_container_width=True)

    rc1, rc2 = st.columns(2)
    with rc1: st.plotly_chart(revenue_pacing_bar(bod), use_container_width=True)
    with rc2: st.plotly_chart(cost_pacing_bar(bod), use_container_width=True)

    st.markdown("---")

    # ── Needs Attention ────────────────────────────────────────────────────
    attention = bod[bod["status"].isin(["Behind","At Risk","Blocked"])].copy()
    n_att     = len(attention)

    st.markdown(
        f"### 🚨 Needs Attention &nbsp;<span style='font-size:13px;color:#557888;font-weight:400'>"
        f"({n_att} initiative{'s' if n_att!=1 else ''} — Status is **Behind**, **At Risk**, or **Blocked**)</span>",
        unsafe_allow_html=True
    )

    if attention.empty:
        st.success("No initiatives currently behind, at risk, or blocked. ✅")
    else:
        # Sort by severity
        attention["_sev"] = attention["status"].map(STATUS_SEV).fillna(9)
        attention = attention.sort_values(["_sev","name"])

        for _, row in attention.iterrows():
            _needs_attention_card(row, user)

    st.markdown("---")

    # ── Recently Updated ───────────────────────────────────────────────────
    st.markdown("### 🕐 Recently Updated")
    recent = bod[bod["last_updated_by"].notna()].head(8)
    if not recent.empty:
        disp = recent[["name","status","pct_complete","owner","last_updated_by"]].copy()
        disp.columns = ["Initiative","Status","% Complete","Owner","Last Updated By"]
        disp["% Complete"] = disp["% Complete"].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "—")
        st.dataframe(disp, use_container_width=True, hide_index=True)


def _needs_attention_card(row: pd.Series, current_user: str):
    """
    Expandable Needs Attention card with crucial fields + inline edit.
    Crucial: Status, % Complete, Next Action, Blocker, Financial Attainment %.
    """
    iid    = str(row.get("id",""))
    status = row.get("status","")
    color  = STATUS_COLORS.get(status,"#aac4d4")
    icon   = STATUS_ICONS.get(status,"⚪")
    pct    = float(row.get("pct_complete",0) or 0)
    name   = row.get("name","")
    owner  = row.get("owner","—")
    target = fmt_date(row.get("target_completion"))
    bl     = str(row.get("blockers","") or "").strip()
    na     = str(row.get("next_action","") or "").strip()

    # Financial attainment badges
    att_ebitda = _attainment_badge(row.get("realized_ebitda"), row.get("forecasted_ebitda"), "EBITDA")
    att_rev    = _attainment_badge(row.get("realized_revenue"), row.get("forecasted_revenue"), "Rev")

    fin_badges = " ".join(filter(None, [att_ebitda, att_rev]))

    expander_label = f"{icon} {name}  ·  {owner}  ·  {pct:.0f}%  ·  {target}"
    with st.expander(expander_label, expanded=False):

        # ── Crucial fields row ──────────────────────────────────────────
        st.markdown(f"""
        <div style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:center;
                      margin-bottom:6px;flex-wrap:wrap;gap:6px">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <span style="background:{color}18;color:{color};padding:3px 10px;border-radius:99px;
                           font-size:12px;font-weight:700;border:1px solid {color}44">{icon} {status}</span>
              {fin_badges}
            </div>
            <div style="font-size:11px;color:#557888">
              Sponsor: {row.get('sponsor','—')} · Target: {target}
            </div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:11px;
                      color:#557888;margin-bottom:3px">
            <span>Progress</span><span style="font-weight:700;color:{color}">{pct:.0f}%</span>
          </div>
          <div style="height:7px;background:#e8eff4;border-radius:99px;overflow:hidden;margin-bottom:10px">
            <div style="width:{pct}%;height:100%;background:{color};border-radius:99px"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Next Action and Blocker — always visible, prominent
        if na and na not in ("nan","None"):
            st.markdown(f"""
            <div style="background:#f0f5f8;border-left:3px solid #5a8010;border-radius:0 8px 8px 0;
                        padding:8px 12px;margin-bottom:6px;font-size:13px;color:#0d2535">
              <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;
                           color:#557888;font-weight:700">Next Action</span><br>
              {na}
            </div>""", unsafe_allow_html=True)

        if bl and bl not in ("nan","None"):
            st.markdown(f"""
            <div style="background:#dc262608;border-left:3px solid #dc2626;border-radius:0 8px 8px 0;
                        padding:8px 12px;margin-bottom:6px;font-size:13px;color:#0d2535">
              <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;
                           color:#dc2626;font-weight:700">⚠️ Blocker</span><br>
              {bl}
            </div>""", unsafe_allow_html=True)

        # Secondary detail
        d1,d2,d3,d4 = st.columns(4)
        d1.markdown(f"**Region:** {row.get('region','—')}")
        d2.markdown(f"**Priority:** P{row.get('priority','—')}")
        d3.markdown(f"**Start:** {fmt_date(row.get('start_date'))}")
        d4.markdown(f"**Revised:** {fmt_date(row.get('revised_completion'))}")

        # Financial attainment detail (if any data)
        has_fin = any(row.get(c) for c in ["forecasted_ebitda","forecasted_revenue","forecasted_cost"])
        if has_fin:
            fn1,fn2,fn3,fn4,fn5,fn6 = st.columns(6)
            fn1.metric("Fcst Rev",   fmt_currency(row.get("forecasted_revenue")))
            fn2.metric("Real Rev",   fmt_currency(row.get("realized_revenue")))
            fn3.metric("Fcst EBITDA",fmt_currency(row.get("forecasted_ebitda")))
            fn4.metric("Real EBITDA",fmt_currency(row.get("realized_ebitda")))
            fn5.metric("Fcst Cost",  fmt_currency(row.get("forecasted_cost")))
            fn6.metric("Real Cost",  fmt_currency(row.get("realized_cost")))

        # Inline edit
        st.markdown("---")
        def on_save(fields, _iid=iid):
            if update_initiative(_iid, fields):
                st.success("✅ Saved"); st.rerun()
        def on_delete(_iid=iid, _spid=row.get("sp_id",iid)):
            if delete_initiative(_iid, _spid):
                st.success("Deleted."); st.rerun()

        edit_form(row, current_user, "SLT", on_save, on_delete)
