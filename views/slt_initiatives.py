"""
views/slt_initiatives.py — All Initiatives with sort control + crucial fields.
Sort options: Priority+Severity (default), Target Date, % Complete, Owner, Name.
"""
import streamlit as st
import pandas as pd
from data.loader import load_initiatives, update_initiative, delete_initiative, load_sub_initiatives
from components.ui import fmt_currency, fmt_date, edit_form
from components.filters import render_global_filter
from config.settings import is_sponsor

STATUS_COLORS = {
    "On Track":"#5a8010","At Risk":"#d97706","Behind":"#dc2626",
    "Blocked":"#7c3aed","Completed":"#0369a1","Not Started":"#aac4d4",
}
STATUS_ICONS = {
    "On Track":"🟢","At Risk":"🟡","Behind":"🔴",
    "Blocked":"🟣","Completed":"✅","Not Started":"⚪",
}
# Severity order for default sort (most urgent first)
STATUS_SEV = {"Behind":0,"Blocked":1,"At Risk":2,"Not Started":3,"On Track":4,"Completed":5}

SORT_OPTIONS = {
    "Priority + Severity (default)": "_sort_pri_sev",
    "Target Date (nearest first)":   "target_completion",
    "% Complete (lowest first)":     "pct_complete",
    "Owner A→Z":                     "owner",
    "Name A→Z":                      "name",
}


def _attainment_badge(realized, forecasted, label):
    try:
        if not forecasted or float(forecasted) == 0: return ""
        pct = float(realized or 0) / float(forecasted) * 100
        color = "#5a8010" if pct>=75 else "#d97706" if pct>=50 else "#dc2626"
        return (f'<span style="background:{color}18;color:{color};padding:2px 8px;'
                f'border-radius:99px;font-size:11px;font-weight:700;border:1px solid {color}44">'
                f'{label}&nbsp;{pct:.0f}%</span>')
    except: return ""


def render():
    st.markdown("## 📋 All Initiatives")
    user = st.session_state.current_user

    df_raw   = load_initiatives()
    filtered = render_global_filter(df_raw)

    # ── Sort control ──────────────────────────────────────────────────────
    sc1, sc2 = st.columns([3, 1])
    sc1.caption(
        f"**Showing {len(filtered)} of {len(df_raw)} initiatives** · "
        f"Default sort: P1 first, then Behind→Blocked→At Risk→On Track within each priority"
    )
    sort_choice = sc2.selectbox("Sort by", list(SORT_OPTIONS.keys()),
                                index=0, label_visibility="collapsed", key="ini_sort")
    sort_col    = SORT_OPTIONS[sort_choice]

    for cat, cat_label in [("BOD","🏢 Board / SLT Level"), ("SM","🏭 Site Manufacturing")]:
        subset = filtered[filtered["category"] == cat].copy() if "category" in filtered.columns else filtered.copy()
        if subset.empty:
            continue
        st.markdown(f"### {cat_label} &nbsp;<span style='font-size:13px;color:#557888;font-weight:400'>({len(subset)})</span>",
                    unsafe_allow_html=True)

        # Apply sort
        if sort_col == "_sort_pri_sev":
            subset["_sev"] = subset["status"].map(STATUS_SEV).fillna(9)
            subset["_pri"] = pd.to_numeric(subset["priority"], errors="coerce").fillna(9)
            subset = subset.sort_values(["_pri","_sev","name"])
        else:
            asc = sort_col != "pct_complete"   # % complete: lowest first = ascending
            subset = subset.sort_values(sort_col, ascending=asc, na_position="last")

        for _, row in subset.iterrows():
            _render_row(row, user)

        st.markdown("---")


def _render_row(row: pd.Series, current_user: str):
    iid    = str(row.get("id",""))
    name   = row.get("name","Unnamed")
    status = row.get("status","")
    pct    = float(row.get("pct_complete",0) or 0)
    color  = STATUS_COLORS.get(status,"#aac4d4")
    icon   = STATUS_ICONS.get(status,"⚪")
    owner  = row.get("owner","—")
    target = fmt_date(row.get("target_completion"))
    na     = str(row.get("next_action","") or "").strip()
    bl     = str(row.get("blockers","") or "").strip()

    att_ebitda = _attainment_badge(row.get("realized_ebitda"), row.get("forecasted_ebitda"), "EBITDA")
    att_rev    = _attainment_badge(row.get("realized_revenue"), row.get("forecasted_revenue"), "Rev")
    fin_badges = " ".join(filter(None, [att_ebitda, att_rev]))

    expander_label = f"{icon} {name}  ·  {owner}  ·  {pct:.0f}%  ·  {target}"

    with st.expander(expander_label, expanded=False):

        # ── Crucial fields — top of every expanded row ──────────────────
        st.markdown(f"""
        <div style="margin-bottom:8px">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px">
            <span style="background:{color}18;color:{color};padding:3px 10px;border-radius:99px;
                         font-size:12px;font-weight:700;border:1px solid {color}44">{icon} {status}</span>
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

        # Next Action — prominent
        if na and na not in ("nan","None"):
            st.markdown(f"""
            <div style="background:#f0f5f8;border-left:3px solid #5a8010;border-radius:0 8px 8px 0;
                        padding:8px 12px;margin-bottom:6px;font-size:13px;color:#0d2535">
              <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;
                           color:#557888;font-weight:700">Next Action</span><br>
              {na}
            </div>""", unsafe_allow_html=True)

        # Blocker — prominent, red
        if bl and bl not in ("nan","None"):
            st.markdown(f"""
            <div style="background:#dc262608;border-left:3px solid #dc2626;border-radius:0 8px 8px 0;
                        padding:8px 12px;margin-bottom:6px;font-size:13px;color:#0d2535">
              <span style="font-size:10px;text-transform:uppercase;letter-spacing:0.08em;
                           color:#dc2626;font-weight:700">⚠️ Blocker</span><br>
              {bl}
            </div>""", unsafe_allow_html=True)

        # Secondary meta
        d1,d2,d3,d4 = st.columns(4)
        d1.markdown(f"**Sponsor:** {row.get('sponsor','—')}")
        d2.markdown(f"**Region:** {row.get('region','—')}")
        d3.markdown(f"**Priority:** P{row.get('priority','—')}")
        d4.markdown(f"**Target:** {target}")

        if row.get("description","").strip() and str(row.get("description","")) not in ("nan","None"):
            desc = str(row.get("description","")).replace("'", "&#39;")
            st.markdown(f"""
            <details style="margin-bottom:6px">
              <summary style="font-size:12px;color:#557888;cursor:pointer;
                              list-style:none;padding:4px 0">
                📄 Full Description ▸
              </summary>
              <div style="font-size:13px;color:#294c60;padding:6px 0 2px">{desc}</div>
            </details>""", unsafe_allow_html=True)

        if str(row.get("completed_actions","")).strip() not in ("","nan","None"):
            st.markdown(f"**✅ Completed Actions:** {row.get('completed_actions','')}")

        # Financial attainment metrics
        has_fin = any(row.get(c) for c in ["forecasted_ebitda","forecasted_revenue","forecasted_cost"])
        if has_fin:
            st.markdown("**📊 Financial Attainment**")
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
                    <div style="background:#f0f5f8;border:1px solid #cddde7;border-left:2px solid {sc};
                                border-radius:0 6px 6px 0;padding:6px 12px;margin:3px 0;font-size:12px;color:#294c60">
                      {STATUS_ICONS.get(sub.get('status',''),'⚪')} <b>{sub.get('name','')}</b>
                      · {sub.get('owner','—')} · Due: {fmt_date(sub.get('due_date'))}
                    </div>""", unsafe_allow_html=True)

        # Inline edit
        st.markdown("---")
        def on_save(fields, _iid=iid):
            if update_initiative(_iid, fields):
                st.success("✅ Saved"); st.rerun()
        def on_delete(_iid=iid, _sp=row.get("sp_id",iid)):
            if delete_initiative(_iid, _sp):
                st.success("Deleted."); st.rerun()
        edit_form(row, current_user, "SLT", on_save, on_delete)
