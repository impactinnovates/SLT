"""
components/ui.py
Reusable Streamlit UI components — DemandPulse color scheme.
"""
import streamlit as st
import pandas as pd
from datetime import date, datetime
from config.settings import get_permissions, is_sponsor

# ── DemandPulse palette ───────────────────────────────────────────────────
DP = {
    "bg":      "#f0f5f8",
    "card":    "#ffffff",
    "navy":    "#0d2535",
    "navy2":   "#294c60",
    "teal":    "#557888",
    "teal2":   "#7a9aaa",
    "border":  "#cddde7",
    "border2": "#aac4d4",
    "accent":  "#5a8010",
    "accent2": "#8fb832",
    "panel":   "#e8eff4",
}

STATUS_COLORS = {
    "On Track":    "#5a8010",
    "At Risk":     "#d97706",
    "Behind":      "#dc2626",
    "Blocked":     "#7c3aed",
    "Completed":   "#0369a1",
    "Not Started": "#557888",
}

STATUS_ICONS = {
    "On Track":    "🟢",
    "At Risk":     "🟡",
    "Behind":      "🔴",
    "Blocked":     "🟣",
    "Completed":   "✅",
    "Not Started": "⚪",
}

PRIORITY_COLORS = {
    "1": "#dc2626",
    "2": "#d97706",
    "3": "#5a8010",
}


def _safe_str(val) -> str:
    """Convert a value to string, returning empty string for None/NaN."""
    if val is None:
        return ""
    if isinstance(val, float) and val != val:   # NaN check
        return ""
    s = str(val).strip()
    return "" if s in ("nan", "None", "none", "NaN") else s


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, DP["teal"])
    icon  = STATUS_ICONS.get(status, "⚪")
    return (f'<span style="background:{color}18;color:{color};padding:2px 10px;'
            f'border-radius:99px;font-size:11px;font-weight:700;'
            f'border:1px solid {color}44">{icon} {status}</span>')


def priority_badge(priority: str) -> str:
    labels = {"1": "P1 — Critical", "2": "P2 — High", "3": "P3 — Standard"}
    color  = PRIORITY_COLORS.get(str(priority), DP["teal"])
    label  = labels.get(str(priority), f"P{priority}")
    return (f'<span style="background:{color}18;color:{color};padding:2px 8px;'
            f'border-radius:5px;font-size:10px;font-weight:700;'
            f'border:1px solid {color}33">{label}</span>')


def fmt_currency(val) -> str:
    if val is None or (isinstance(val, float) and val != val):
        return "—"
    return f"${val:,.0f}"


def fmt_pct(val) -> str:
    if val is None:
        return "—"
    return f"{val:.0f}%"


def fmt_date(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, (date, datetime)):
        return val.strftime("%b %d, %Y")
    return str(val)


def metric_card(label: str, value: str, delta: str = None, color: str = None):
    """Styled metric tile matching DemandPulse card style."""
    c = color or DP["accent"]
    delta_html = (
        f'<div style="font-size:11px;color:{DP["teal"]};margin-top:3px">'
        f'{delta}</div>'
    ) if delta else ""
    st.markdown(f"""
    <div style="background:{DP['card']};border:1px solid {DP['border']};
                border-radius:10px;padding:14px 16px;
                border-left:3px solid {c};
                box-shadow:0 1px 4px rgba(13,37,53,0.06)">
      <div style="font-size:10px;color:{DP['teal']};text-transform:uppercase;
                  letter-spacing:0.1em;margin-bottom:5px;font-weight:600">{label}</div>
      <div style="font-size:24px;font-weight:800;color:{DP['navy']};
                  font-family:'Syne',sans-serif">{value}</div>
      {delta_html}
    </div>
    """, unsafe_allow_html=True)


def edit_form(row: pd.Series, current_user: str, role: str, on_save, on_delete=None):
    """Edit form for an initiative. Fields shown depend on role."""
    perms = get_permissions(role)

    with st.form(key=f"edit_{row.get('id','new')}"):
        st.subheader("Edit Initiative" if row.get("id") else "New Initiative")

        name = st.text_input("Initiative Name *", value=_safe_str(row.get("name")))

        c1, c2 = st.columns(2)
        statuses   = ["On Track","At Risk","Behind","Blocked","Not Started","Completed"]
        cur_status = _safe_str(row.get("status")) or "On Track"
        status     = c1.selectbox("Status", statuses,
                                   index=statuses.index(cur_status)
                                         if cur_status in statuses else 0)

        raw_pct = row.get("pct_complete", 0)
        pct_val = 0 if raw_pct is None or (isinstance(raw_pct, float) and raw_pct != raw_pct) \
                    else int(raw_pct)
        pct = c2.slider("% Complete", 0, 100, pct_val)

        next_action       = st.text_area("Next Action",
                                          value=_safe_str(row.get("next_action")), height=80)
        completed_actions = st.text_area("Completed Actions",
                                          value=_safe_str(row.get("completed_actions")), height=80)
        blockers          = st.text_area("Blockers",
                                          value=_safe_str(row.get("blockers")), height=60)

        if perms.get("view_financials"):
            st.markdown("---")
            st.markdown("**Financial Actuals**")
            fa1, fa2, fa3 = st.columns(3)
            realized_rev    = fa1.text_input("Realized Revenue",
                                              value=_safe_str(row.get("realized_revenue")))
            realized_ebitda = fa2.text_input("Realized EBITDA",
                                              value=_safe_str(row.get("realized_ebitda")))
            realized_cost   = fa3.text_input("Realized Cost",
                                              value=_safe_str(row.get("realized_cost")))
            st.markdown("**Financial Forecasts**")
            ff1, ff2, ff3 = st.columns(3)
            fcst_rev    = ff1.text_input("Forecasted Revenue",
                                          value=_safe_str(row.get("forecasted_revenue")))
            fcst_ebitda = ff2.text_input("Forecasted EBITDA",
                                          value=_safe_str(row.get("forecasted_ebitda")))
            fcst_cost   = ff3.text_input("Forecasted Cost",
                                          value=_safe_str(row.get("forecasted_cost")))

        col_s, col_d = st.columns([3, 1])
        save = col_s.form_submit_button("💾 Save Changes",
                                         use_container_width=True, type="primary")
        show_delete = (on_delete is not None
                       and is_sponsor(current_user)
                       and row.get("sponsor","") == current_user)
        delete = col_d.form_submit_button("🗑 Delete",
                                           use_container_width=True) if show_delete else False

    if save and name.strip():
        from data.models import parse_currency
        updated = {
            "name":              name.strip(),
            "status":            status,
            "pct_complete":      pct,
            "next_action":       next_action,
            "completed_actions": completed_actions,
            "blockers":          blockers,
            "last_updated_by":   current_user,
        }
        if perms.get("view_financials"):
            updated.update({
                "realized_revenue":   parse_currency(realized_rev),
                "realized_ebitda":    parse_currency(realized_ebitda),
                "realized_cost":      parse_currency(realized_cost),
                "forecasted_revenue": parse_currency(fcst_rev),
                "forecasted_ebitda":  parse_currency(fcst_ebitda),
                "forecasted_cost":    parse_currency(fcst_cost),
            })
        on_save(updated)

    if delete and show_delete and on_delete:
        on_delete()
