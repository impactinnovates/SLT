"""
pages/tm_tasks.py
Team Member view — only shows sub-tasks explicitly assigned to this user.
TMs cannot see any BOD or SM initiatives, only their own task list.
"""
import streamlit as st
import pandas as pd
from datetime import date
from data.loader import load_sub_initiatives, save_sub_initiatives
from data.models import STATUS_COLORS, STATUS_ICONS
from components.ui import fmt_date


def render():
    st.markdown("## ✅ My Tasks")
    user = st.session_state.current_user

    sub_df = load_sub_initiatives()

    if sub_df.empty or "owner" not in sub_df.columns:
        st.info("No tasks assigned to you yet. Check back after your manager has set up your task list.")
        return

    my_tasks = sub_df[sub_df["owner"] == user].copy()

    if my_tasks.empty:
        st.info(f"No tasks currently assigned to {user}. Your manager will assign tasks here.")
        return

    # ── Stats ─────────────────────────────────────────────────────────────
    total     = len(my_tasks)
    done      = (my_tasks["status"] == "Completed").sum()
    in_prog   = (my_tasks["status"] == "On Track").sum()
    overdue   = my_tasks[
        my_tasks["due_date"].notna() &
        (my_tasks["status"] != "Completed")
    ].apply(lambda r: _is_overdue(r.get("due_date")), axis=1).sum()

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Tasks",    total)
    c2.metric("Completed",      done)
    c3.metric("In Progress",    in_prog)
    c4.metric("Overdue",        int(overdue), delta=None)

    st.markdown("---")

    show_done = st.toggle("Show Completed Tasks", value=False)
    if not show_done:
        my_tasks = my_tasks[my_tasks["status"] != "Completed"]

    if my_tasks.empty:
        st.success("🎉 All tasks completed!")
        return

    # ── Task list ─────────────────────────────────────────────────────────
    for _, task in my_tasks.sort_values("due_date", na_position="last").iterrows():
        _render_task_card(task, sub_df, user)


def _is_overdue(due_val) -> bool:
    if not due_val or str(due_val).strip() in ("","None","nan"):
        return False
    from data.models import parse_date
    d = parse_date(str(due_val))
    return d is not None and d < date.today()


def _render_task_card(task: pd.Series, full_df: pd.DataFrame, current_user: str):
    tid    = str(task.get("id",""))
    name   = task.get("name","Unnamed Task")
    status = task.get("status","")
    pct    = float(task.get("pct_complete", 0) or 0)
    color  = STATUS_COLORS.get(status,"#64748B")
    icon   = STATUS_ICONS.get(status,"⚪")
    due    = fmt_date(task.get("due_date"))
    od     = _is_overdue(task.get("due_date")) and status != "Completed"

    due_html = (
        f'<span style="color:#EF4444;font-weight:700">⚠️ Overdue: {due}</span>'
        if od else
        f'<span style="color:#64748B">📅 Due: {due}</span>'
    )

    with st.expander(f"{icon} {name}  ·  {due}", expanded=od):
        # Progress bar
        st.markdown(f"""
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:11px;
                      color:#94A3B8;margin-bottom:3px">
            <span>Progress</span><span>{pct:.0f}%</span>
          </div>
          <div style="height:6px;background:#1E293B;border-radius:99px;overflow:hidden">
            <div style="width:{pct}%;height:100%;background:{color};border-radius:99px"></div>
          </div>
          <div style="margin-top:6px;font-size:12px">{due_html}</div>
        </div>
        """, unsafe_allow_html=True)

        if task.get("description","").strip():
            st.markdown(f"**Description:** {task.get('description','')}")
        if task.get("next_action","").strip():
            st.markdown(f"**→ Next Action:** {task.get('next_action','')}")
        if task.get("blockers","").strip():
            st.warning(f"⚠️ **Blocker:** {task.get('blockers','')}")

        # TM can update status, progress, next action, blockers only
        st.markdown("**Update Progress**")
        with st.form(key=f"tm_edit_{tid}"):
            new_status  = st.selectbox("Status",
                ["Not Started","On Track","At Risk","Behind","Blocked","Completed"],
                index=["Not Started","On Track","At Risk","Behind","Blocked","Completed"].index(status)
                      if status in ["Not Started","On Track","At Risk","Behind","Blocked","Completed"] else 0)
            new_pct     = st.slider("% Complete", 0, 100, int(pct))
            new_next    = st.text_area("Next Action", value=task.get("next_action",""), height=60)
            new_blocker = st.text_input("Blocker (if any)", value=task.get("blockers",""))

            if st.form_submit_button("💾 Save Update", type="primary", use_container_width=True):
                # Update in DataFrame
                idx = full_df[full_df["id"] == tid].index
                if len(idx) > 0:
                    full_df.loc[idx[0], "status"]      = new_status
                    full_df.loc[idx[0], "pct_complete"] = new_pct
                    full_df.loc[idx[0], "next_action"]  = new_next
                    full_df.loc[idx[0], "blockers"]     = new_blocker
                    save_sub_initiatives(full_df)
                    st.success("✅ Updated")
                    st.rerun()
