"""
components/filters.py
Global multi-select filter bar — persists across all SLT pages via session_state.
Sponsor/Owner use OR logic — a row matches if it appears in EITHER selected list.
All other filters use AND logic.
"""
import streamlit as st
import pandas as pd

_DEFAULTS = {
    "gf_category":       [],
    "gf_status":         [],
    "gf_sponsor":        [],
    "gf_owner":          [],
    "gf_region":         [],
    "gf_show_completed": True,
}


def _init():
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_global_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renders global multi-select filter bar and returns filtered DataFrame.
    Call once at the top of each SLT view.
    Selections persist in session_state across page navigation.

    Sponsor + Owner share OR logic: a row is included if the person appears
    in EITHER the selected sponsors OR the selected owners. This handles
    people like Chad who appear in both lists.
    """
    _init()

    sponsors   = sorted(df["sponsor"].dropna().unique().tolist())
    owners     = sorted(df["owner"].dropna().unique().tolist())
    statuses   = sorted(df["status"].dropna().unique().tolist())
    regions    = sorted(df["region"].dropna().unique().tolist())
    categories = sorted(df["category"].dropna().unique().tolist())

    # Count active filters for badge
    n_active = sum([
        len(st.session_state.gf_category) > 0,
        len(st.session_state.gf_status)   > 0,
        len(st.session_state.gf_sponsor)  > 0,
        len(st.session_state.gf_owner)    > 0,
        len(st.session_state.gf_region)   > 0,
    ])
    badge = f" ({n_active} active)" if n_active else ""

    with st.expander(f"🔍 Global Filters{badge}", expanded=n_active > 0):
        r1c1, r1c2, r1c3 = st.columns(3)
        r2c1, r2c2, r2c3 = st.columns(3)

        st.session_state.gf_sponsor = r1c1.multiselect(
            "Sponsor", sponsors,
            default=[s for s in st.session_state.gf_sponsor if s in sponsors],
            placeholder="All sponsors…", key="_ms_spon"
        )
        st.session_state.gf_owner = r1c2.multiselect(
            "Owner", owners,
            default=[o for o in st.session_state.gf_owner if o in owners],
            placeholder="All owners…", key="_ms_own"
        )
        st.session_state.gf_region = r1c3.multiselect(
            "Region", regions,
            default=[r for r in st.session_state.gf_region if r in regions],
            placeholder="All regions…", key="_ms_reg"
        )
        st.session_state.gf_status = r2c1.multiselect(
            "Status", statuses,
            default=[s for s in st.session_state.gf_status if s in statuses],
            placeholder="All statuses…", key="_ms_stat"
        )
        st.session_state.gf_category = r2c2.multiselect(
            "Category", categories,
            default=[c for c in st.session_state.gf_category if c in categories],
            placeholder="All categories…", key="_ms_cat"
        )

        col_tog, col_clr = r2c3.columns([1, 1])
        with col_tog:
            st.session_state.gf_show_completed = st.toggle(
                "Show Completed",
                value=st.session_state.gf_show_completed,
                key="_tog_comp"
            )
        with col_clr:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("✕ Clear All", use_container_width=True, key="_clr_btn"):
                for k, v in _DEFAULTS.items():
                    st.session_state[k] = v if not isinstance(v, list) else []
                st.rerun()

        # Active filter summary
        parts = []
        if st.session_state.gf_sponsor:
            parts.append("Sponsor: " + ", ".join(st.session_state.gf_sponsor))
        if st.session_state.gf_owner:
            parts.append("Owner: " + ", ".join(st.session_state.gf_owner))
        if st.session_state.gf_region:
            parts.append("Region: " + ", ".join(st.session_state.gf_region))
        if st.session_state.gf_status:
            parts.append("Status: " + ", ".join(st.session_state.gf_status))
        if st.session_state.gf_category:
            parts.append("Category: " + ", ".join(st.session_state.gf_category))
        if parts:
            st.caption("Active: " + " · ".join(parts))

    # ── Apply filters ──────────────────────────────────────────────────────
    mask = pd.Series([True] * len(df), index=df.index)

    # Sponsor + Owner: OR logic — include if person in either list
    sel_spon  = st.session_state.gf_sponsor
    sel_own   = st.session_state.gf_owner
    if sel_spon or sel_own:
        spon_mask = df["sponsor"].isin(sel_spon) if sel_spon else pd.Series([False]*len(df), index=df.index)
        own_mask  = df["owner"].isin(sel_own)    if sel_own  else pd.Series([False]*len(df), index=df.index)
        mask &= (spon_mask | own_mask)

    # Other filters: AND logic
    if st.session_state.gf_status:
        mask &= df["status"].isin(st.session_state.gf_status)
    if st.session_state.gf_region:
        mask &= df["region"].isin(st.session_state.gf_region)
    if st.session_state.gf_category:
        mask &= df["category"].isin(st.session_state.gf_category)
    if not st.session_state.gf_show_completed:
        mask &= df["status"] != "Completed"

    return df[mask].copy()
