"""
pages/pm_subtasks.py — PM sub-task management
"""
import streamlit as st
import pandas as pd
from data.loader import load_initiatives, load_sub_initiatives, save_sub_initiatives
from components.ui import fmt_date
from data.models import STATUS_COLORS, STATUS_ICONS
import uuid


def render():
    st.markdown("## ✅ Sub-Tasks")
    st.caption("Create and manage sub-tasks for your team members (TM layer)")
    user = st.session_state.current_user

    df    = load_initiatives()
    sm    = df[(df["category"] == "SM") & (df["owner"] == user)].copy()
    sub_df = load_sub_initiatives()

    if sm.empty:
        st.info("No SM initiatives assigned to you yet.")
        return

    for _, row in sm.iterrows():
        iid  = str(row.get("id",""))
        name = row.get("name","Unnamed")

        with st.expander(f"📌 {name}", expanded=False):
            # Existing sub-tasks
            if not sub_df.empty and "parent_id" in sub_df.columns:
                subs = sub_df[sub_df["parent_id"] == iid]
                if not subs.empty:
                    for _, sub in subs.iterrows():
                        sc = STATUS_COLORS.get(sub.get("status",""),"#64748B")
                        s1,s2,s3 = st.columns([3,1,1])
                        s1.markdown(f"{STATUS_ICONS.get(sub.get('status',''),'⚪')} **{sub.get('name','')}**  ·  {sub.get('owner','—')}")
                        s2.markdown(fmt_date(sub.get("due_date")))
                        s3.markdown(f"`{sub.get('status','')}`")

            # Add new sub-task form
            st.markdown("**Add Sub-Task**")
            with st.form(key=f"sub_{iid}"):
                sn = st.text_input("Task Name *")
                sc1,sc2,sc3 = st.columns(3)
                s_owner  = sc1.text_input("Assign To (TM name)")
                s_due    = sc2.date_input("Due Date")
                s_status = sc3.selectbox("Status", ["Not Started","On Track","At Risk","Behind","Blocked"])
                s_desc   = st.text_area("Description", height=60)
                if st.form_submit_button("Add Sub-Task", type="primary"):
                    if sn.strip():
                        new_row = {
                            "id":          str(uuid.uuid4()),
                            "parent_id":   iid,
                            "name":        sn.strip(),
                            "description": s_desc,
                            "owner":       s_owner,
                            "status":      s_status,
                            "pct_complete":0,
                            "due_date":    str(s_due),
                            "created_by":  user,
                            "next_action": "",
                            "blockers":    "",
                            "sp_id":       "",
                        }
                        updated = pd.concat([sub_df, pd.DataFrame([new_row])], ignore_index=True)
                        save_sub_initiatives(updated)
                        st.success(f"✅ Sub-task '{sn}' added.")
                        st.rerun()
                    else:
                        st.error("Task name required.")


"""
pages/pm_new_subtask.py
"""
def render_new():
    st.markdown("## ➕ New Sub-Task")
    st.info("Use the Sub-Tasks page to add tasks under a specific initiative.")
