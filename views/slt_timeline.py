"""
views/slt_timeline.py
Two-mode timeline with expandable initiative detail + inline edit.

Mode 1 (default): Due Soon — initiatives grouped by urgency into section headers.
                  Each initiative is a st.expander with full detail and edit form.
Mode 2: Gantt    — horizontal bar chart for visual project spanning.

NOTE: Buckets are rendered as section headers (not expanders) so each
      initiative can safely use its own st.expander without nesting.
"""
import streamlit as st
import pandas as pd
from datetime import date
from data.loader import load_initiatives, update_initiative, delete_initiative, load_sub_initiatives
from utils.pacing import enrich_dataframe
from components.financial_charts import completion_timeline
from components.filters import render_global_filter
from components.ui import fmt_currency, fmt_date, edit_form

STATUS_COLORS = {
    "On Track":    "#5a8010",
    "At Risk":     "#d97706",
    "Behind":      "#dc2626",
    "Blocked":     "#7c3aed",
    "Completed":   "#0369a1",
    "Not Started": "#aac4d4",
}
STATUS_ICONS = {
    "On Track":    "🟢",
    "At Risk":     "🟡",
    "Behind":      "🔴",
    "Blocked":     "🟣",
    "Completed":   "✅",
    "Not Started": "⚪",
}

BUCKETS = [
    ("🔴 Overdue",        "overdue", "#dc2626"),
    ("🟠 Due ≤ 30 Days",  "30d",     "#d97706"),
    ("🟡 Due 31–90 Days", "90d",     "#f59e0b"),
    ("🟢 Due > 90 Days",  "future",  "#5a8010"),
    ("✅ Completed",      "done",    "#0369a1"),
]


def _bucket(row, today):
    status = row.get("status","")
    if status == "Completed":
        return "done"
    t = row.get("target_completion")
    if not t:
        return "future"
    delta = (t - today).days
    if delta < 0:   return "overdue"
    if delta <= 30: return "30d"
    if delta <= 90: return "90d"
    return "future"


def _days_badge(row, today):
    t = row.get("target_completion")
    if not t: return ""
    delta = (t - today).days
    if row.get("status") == "Completed":
        return (f'<span style="background:#0369a118;color:#0369a1;padding:2px 8px;'
                f'border-radius:99px;font-size:11px;font-weight:700;border:1px solid #0369a144">'
                f'✅ Complete</span>')
    if delta < 0:
        return (f'<span style="background:#dc262618;color:#dc2626;padding:2px 8px;'
                f'border-radius:99px;font-size:11px;font-weight:700;border:1px solid #dc262644">'
                f'⚠️ {abs(delta)}d overdue</span>')
    if delta == 0:
        return (f'<span style="background:#d9770618;color:#d97706;padding:2px 8px;'
                f'border-radius:99px;font-size:11px;font-weight:700;border:1px solid #d9770644">'
                f'Due today</span>')
    color = "#dc2626" if delta<=30 else "#d97706" if delta<=90 else "#5a8010"
    return (f'<span style="background:{color}18;color:{color};padding:2px 8px;'
            f'border-radius:99px;font-size:11px;font-weight:700;border:1px solid {color}44">'
            f'{delta}d remaining</span>')


def _attainment_badge(realized, forecasted, label):
    try:
        if not forecasted or float(forecasted) == 0: return ""
        pct   = float(realized or 0) / float(forecasted) * 100
        color = "#5a8010" if pct>=75 else "#d97706" if pct>=50 else "#dc2626"
        return (f'<span style="background:{color}18;color:{color};padding:2px 8px;'
                f'border-radius:99px;font-size:11px;font-weight:700;border:1px solid {color}44">'
                f'{label}&nbsp;{pct:.0f}%</span>')
    except: return ""


def _initiative_expander(row: pd.Series, today: date, current_user: str):
    """
    st.expander for a single initiative — crucial fields up front, full edit form inside.
    Safe to use because bucket groups are section headers, not expanders.
    """
    iid    = str(row.get("id",""))
    name   = row.get("name","Unnamed")
    status = row.get("status","")
    pct    = float(row.get("pct_complete", 0) or 0)
    color  = STATUS_COLORS.get(status, "#aac4d4")
    icon   = STATUS_ICONS.get(status, "⚪")
    owner  = row.get("owner","—")
    target = fmt_date(row.get("target_completion"))
    na     = str(row.get("next_action","") or "").strip()
    bl     = str(row.get("blockers","") or "").strip()
    days   = _days_badge(row, today)

    att_ebitda = _attainment_badge(row.get("realized_ebitda"), row.get("forecasted_ebitda"), "EBITDA")
    att_rev    = _attainment_badge(row.get("realized_revenue"), row.get("forecasted_revenue"), "Rev")
    fin_badges = " ".join(filter(None, [att_ebitda, att_rev]))

    expander_label = f"{icon} {name}  ·  {owner}  ·  {pct:.0f}%  ·  {target}"

    with st.expander(expander_label, expanded=False):

        # ── Crucial fields ─────────────────────────────────────────────
        st.markdown(f"""
        <div style="margin-bottom:8px">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">
            <span style="background:{color}18;color:{color};padding:3px 10px;border-radius:99px;
                         font-size:12px;font-weight:700;border:1px solid {color}44">{icon} {status}</span>
            {days}
            {fin_badges}
          </div>
          <div style="display:flex;justify-content:space-between;font-size:11px;
                      color:#557888;margin-bottom:3px">
            <span>Progress</span>
            <span style="font-weight:700;color:{color}">{pct:.0f}%</span>
          </div>
          <div style="height:7px;background:#e8eff4;border-radius:99px;overflow:hidden;margin-bottom:8px">
            <div style="width:{pct}%;height:100%;background:{color};border-radius:99px"></div>
          </div>
        </div>""", unsafe_allow_html=True)

        if na and na not in ("nan","None"):
            st.markdown(f"""
            <div style="background:#f0f5f8;border-left:3px solid #5a8010;border-radius:0 8px 8px 0;
                        padding:8px 12px;margin-bottom:6px;font-size:13px;color:#0d2535">
              <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;
                           color:#557888;font-weight:700">Next Action</span><br>{na}
            </div>""", unsafe_allow_html=True)

        if bl and bl not in ("nan","None"):
            st.markdown(f"""
            <div style="background:#dc262608;border-left:3px solid #dc2626;border-radius:0 8px 8px 0;
                        padding:8px 12px;margin-bottom:6px;font-size:13px;color:#0d2535">
              <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;
                           color:#dc2626;font-weight:700">⚠️ Blocker</span><br>{bl}
            </div>""", unsafe_allow_html=True)

        # Secondary meta
        d1,d2,d3,d4 = st.columns(4)
        d1.markdown(f"**Sponsor:** {row.get('sponsor','—')}")
        d2.markdown(f"**Region:** {row.get('region','—')}")
        d3.markdown(f"**Priority:** P{row.get('priority','—')}")
        d4.markdown(f"**Start:** {fmt_date(row.get('start_date'))}")

        # Financial detail
        has_fin = any(row.get(c) for c in ["forecasted_ebitda","forecasted_revenue","forecasted_cost"])
        if has_fin:
            fn1,fn2,fn3,fn4,fn5,fn6 = st.columns(6)
            fn1.metric("Fcst Rev",    fmt_currency(row.get("forecasted_revenue")))
            fn2.metric("Real Rev",    fmt_currency(row.get("realized_revenue")))
            fn3.metric("Fcst EBITDA", fmt_currency(row.get("forecasted_ebitda")))
            fn4.metric("Real EBITDA", fmt_currency(row.get("realized_ebitda")))
            fn5.metric("Fcst Cost",   fmt_currency(row.get("forecasted_cost")))
            fn6.metric("Real Cost",   fmt_currency(row.get("realized_cost")))

        # Sub-tasks
        sub_df = load_sub_initiatives()
        if not sub_df.empty and "parent_id" in sub_df.columns:
            subs = sub_df[sub_df["parent_id"] == iid]
            if not subs.empty:
                st.markdown(f"**Sub-Tasks ({len(subs)})**")
                for _, sub in subs.iterrows():
                    sc = STATUS_COLORS.get(sub.get("status",""),"#aac4d4")
                    st.markdown(f"""
                    <div style="background:#f0f5f8;border-left:2px solid {sc};border-radius:0 6px 6px 0;
                                padding:6px 12px;margin:3px 0;font-size:12px;color:#294c60">
                      {STATUS_ICONS.get(sub.get('status',''),'⚪')} <b>{sub.get('name','')}</b>
                      · {sub.get('owner','—')} · Due: {fmt_date(sub.get('due_date'))}
                    </div>""", unsafe_allow_html=True)

        # Inline edit
        st.markdown("---")
        def on_save(fields, _iid=iid):
            if update_initiative(_iid, fields):
                st.success("✅ Saved"); st.rerun()
        def on_delete(_iid=iid, _sp=row.get("sp_id", iid)):
            if delete_initiative(_iid, _sp):
                st.success("Deleted."); st.rerun()
        edit_form(row, current_user, "SLT", on_save, on_delete)


def render():
    st.markdown("## 📅 Initiative Timeline")
    user   = st.session_state.current_user
    df_raw = enrich_dataframe(load_initiatives())
    df     = render_global_filter(df_raw)

    # ── Mode toggle ───────────────────────────────────────────────────────
    col_m1, col_m2, _ = st.columns([2, 2, 6])
    with col_m1:
        if st.button("📋 Due Soon View", use_container_width=True,
                     type="primary" if st.session_state.get("tl_mode","due_soon")=="due_soon" else "secondary"):
            st.session_state.tl_mode = "due_soon"
            st.rerun()
    with col_m2:
        if st.button("📊 Gantt View", use_container_width=True,
                     type="primary" if st.session_state.get("tl_mode","due_soon")=="gantt" else "secondary"):
            st.session_state.tl_mode = "gantt"
            st.rerun()
    mode = st.session_state.get("tl_mode","due_soon")

    # ── Gantt ─────────────────────────────────────────────────────────────
    if mode == "gantt":
        sub = df[df["start_date"].notna() & df["target_completion"].notna()].copy()
        if sub.empty:
            st.info("No initiatives with both start and target dates match current filters.")
            return
        st.plotly_chart(completion_timeline(sub), use_container_width=True)
        st.caption(f"{len(sub)} initiatives shown · "
                   "🟢 On Track · 🟡 At Risk · 🔴 Behind · 🟣 Blocked · ✅ Completed · ⚪ Not Started")
        return

    # ── Due Soon (default) ────────────────────────────────────────────────
    today = date.today()
    sub   = df.copy()
    sub["_bucket"] = sub.apply(lambda r: _bucket(r, today), axis=1)

    # ── Summary counts ────────────────────────────────────────────────────
    counts = sub["_bucket"].value_counts()
    s1,s2,s3,s4,s5 = st.columns(5)
    s1.metric("🔴 Overdue",        int(counts.get("overdue",0)))
    s2.metric("🟠 Due ≤ 30 Days",  int(counts.get("30d",0)))
    s3.metric("🟡 Due 31–90 Days", int(counts.get("90d",0)))
    s4.metric("🟢 Due > 90 Days",  int(counts.get("future",0)))
    s5.metric("✅ Completed",       int(counts.get("done",0)))

    st.markdown("---")

    if sub.empty:
        st.info("No initiatives match current filters.")
        return

    # ── Buckets as section headers (NOT expanders — avoids nesting issue) ─
    for bucket_label, bucket_key, bucket_color in BUCKETS:
        bucket_df = sub[sub["_bucket"] == bucket_key].copy()
        if bucket_df.empty:
            continue

        bucket_df = bucket_df.sort_values("target_completion",
                                          ascending=True, na_position="last")

        # Section header with count badge
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:10px;margin:12px 0 6px'>"
            f"<span style='font-size:16px;font-weight:700;color:#0d2535;"
            f"font-family:Syne,sans-serif'>{bucket_label}</span>"
            f"<span style='background:{bucket_color}18;color:{bucket_color};padding:2px 10px;"
            f"border-radius:99px;font-size:11px;font-weight:700;border:1px solid {bucket_color}44'>"
            f"{len(bucket_df)}</span></div>",
            unsafe_allow_html=True
        )

        # Within-bucket sponsor filter for large groups
        if len(bucket_df) > 8:
            col_f, _ = st.columns([2, 4])
            sponsors = ["All"] + sorted(bucket_df["sponsor"].dropna().unique().tolist())
            sel = col_f.selectbox("Filter by Sponsor", sponsors,
                                  key=f"bk_{bucket_key}_spon", label_visibility="collapsed")
            if sel != "All":
                bucket_df = bucket_df[bucket_df["sponsor"] == sel]

        # Each initiative as its own expander — no nesting
        for _, row in bucket_df.iterrows():
            _initiative_expander(row, today, user)

        st.markdown("<hr style='margin:8px 0;border-color:#cddde7'>",
                    unsafe_allow_html=True)
