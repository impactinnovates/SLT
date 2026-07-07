"""
pages/pm_new_subtask.py — Redirect page
"""
import streamlit as st


def render():
    st.markdown("## ➕ New Sub-Task")
    st.info("Navigate to **Sub-Tasks**, expand the parent initiative, and use the Add Sub-Task form at the bottom.")
