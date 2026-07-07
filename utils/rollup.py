"""
utils/rollup.py
Hierarchy + roll-up for the Initiative/Task model.

One List holds both rows; `task_type` says which is which and `parent_id` links a
Task to its parent Initiative's id. This module splits the two, attaches each
initiative's child tasks, and computes rolled-up progress and risk so a parent
reflects the state of its tasks.

Roll-up rules (v1):
  rollup_pct   = mean of child % complete (None if no children)
  rollup_risk  = any child is Behind or Blocked
  effective_pct= the initiative's own % if SLT set one, else the rolled-up %
Roll-up never silently overwrites an SLT-entered %; it fills in when the parent
has tasks and no explicit value, and always travels alongside as rollup_pct so
the UI can show "rolled X% across N tasks".
"""
import pandas as pd

from data.models import TYPE_INITIATIVE, TYPE_TASK

RISK_STATUSES = {"Behind", "Blocked"}


def is_task(row) -> bool:
    return str(row.get("task_type", "")).strip().lower() == TYPE_TASK.lower()


def split_hierarchy(df: pd.DataFrame):
    """Return (initiatives_df, tasks_df). Rows with no task_type default to
    Initiative, matching how the List treats untyped legacy rows."""
    if df.empty or "task_type" not in df.columns:
        return df.copy(), df.iloc[0:0].copy()
    t = df["task_type"].astype(str).str.strip().str.lower()
    tasks = df[t == TYPE_TASK.lower()].copy()
    inits = df[t != TYPE_TASK.lower()].copy()
    return inits, tasks


def children_of(tasks: pd.DataFrame, initiative_id) -> pd.DataFrame:
    if tasks.empty or "parent_id" not in tasks.columns:
        return tasks.iloc[0:0]
    return tasks[tasks["parent_id"].astype(str).str.strip() == str(initiative_id).strip()]


def _rollup_for(children: pd.DataFrame) -> dict:
    n = len(children)
    if n == 0:
        return {"task_count": 0, "tasks_done": 0, "rollup_pct": None,
                "rollup_risk": False, "risk_reason": ""}
    pct = pd.to_numeric(children.get("pct_complete"), errors="coerce")
    done = int((children.get("status") == "Completed").sum())
    risky = children[children.get("status").isin(RISK_STATUSES)] if "status" in children else children.iloc[0:0]
    reason = ""
    if len(risky):
        reason = ", ".join(sorted(risky["status"].unique())) + \
                 f" on {len(risky)} of {n} task{'s' if n != 1 else ''}"
    return {
        "task_count": n,
        "tasks_done": done,
        "rollup_pct": round(float(pct.mean()), 1) if pct.notna().any() else None,
        "rollup_risk": bool(len(risky)),
        "risk_reason": reason,
    }


def attach_rollup(initiatives: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    """Add task_count, tasks_done, rollup_pct, rollup_risk, risk_reason,
    effective_pct to each initiative."""
    if initiatives.empty:
        for c in ("task_count", "tasks_done", "rollup_pct", "rollup_risk",
                  "risk_reason", "effective_pct"):
            initiatives[c] = [] if c not in initiatives else initiatives[c]
        return initiatives

    rows = []
    for _, ini in initiatives.iterrows():
        r = _rollup_for(children_of(tasks, ini.get("id")))
        own = ini.get("pct_complete")
        own_val = None
        try:
            own_val = float(own) if own is not None and str(own) != "" and not (isinstance(own, float) and own != own) else None
        except (TypeError, ValueError):
            own_val = None
        # Effective %: SLT's own value wins; otherwise the rolled-up value.
        r["effective_pct"] = own_val if own_val is not None else r["rollup_pct"]
        rows.append(r)

    roll = pd.DataFrame(rows, index=initiatives.index)
    for c in roll.columns:
        initiatives[c] = roll[c]
    return initiatives


def needs_attention(ini) -> bool:
    """An initiative needs attention if its own status is risky OR any child is."""
    own = str(ini.get("status", "")) in {"Behind", "At Risk", "Blocked"}
    return bool(own or ini.get("rollup_risk"))
