"""
utils/rollup.py
Hierarchy + multi-level roll-up for the Initiative/Task model.

One List holds every row; `task_type` says Initiative vs Task and `parent_id`
links a child to its parent (an Initiative OR another Task). This supports any
depth: sub-task -> task -> initiative.

For every row we compute, over its whole subtree of descendant tasks:
  effective_pct = own % if explicitly set (>0), else the mean of children's
                  effective % (roll-up). SLT/leader entry still overrides.
  rollup_pct    = the pure rolled value (mean of children's effective %), or None
                  for a leaf.
  task_count    = number of DIRECT children (for the "N tasks" label)
  tasks_done    = descendants that are Completed
  rollup_risk   = any descendant task is Behind or Blocked
"""
from collections import defaultdict

import pandas as pd

from data.models import TYPE_INITIATIVE, TYPE_TASK

RISK_STATUSES = {"Behind", "Blocked"}


def is_task(row) -> bool:
    return str(row.get("task_type", "")).strip().lower() == TYPE_TASK.lower()


def split_hierarchy(df: pd.DataFrame):
    """Return (initiatives_df, tasks_df). Untyped rows default to Initiative."""
    if df.empty or "task_type" not in df.columns:
        return df.copy(), df.iloc[0:0].copy()
    t = df["task_type"].astype(str).str.strip().str.lower()
    return df[t != TYPE_TASK.lower()].copy(), df[t == TYPE_TASK.lower()].copy()


def children_of(tasks: pd.DataFrame, parent_id) -> pd.DataFrame:
    if tasks.empty or "parent_id" not in tasks.columns:
        return tasks.iloc[0:0]
    return tasks[tasks["parent_id"].astype(str).str.strip() == str(parent_id).strip()]


def _num_pct(v):
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def attach_rollup(df: pd.DataFrame) -> pd.DataFrame:
    """Add subtree roll-up columns to EVERY row (initiatives and tasks alike),
    so both initiative cards and the task workspace reflect nested progress."""
    cols = ("task_count", "tasks_done", "rollup_pct", "rollup_risk",
            "risk_reason", "effective_pct")
    if df.empty:
        for c in cols:
            if c not in df.columns:
                df[c] = pd.Series(dtype=object)
        return df

    df = df.copy()
    ids = df["id"].astype(str).tolist()
    rows = {str(r["id"]): r for _, r in df.iterrows()}
    children = defaultdict(list)
    for rid, r in rows.items():
        pid = str(r.get("parent_id", "")).strip()
        if pid and pid != rid and pid in rows:
            children[pid].append(rid)

    eff_memo: dict = {}

    def effective(nid, seen=()):
        if nid in eff_memo:
            return eff_memo[nid]
        if nid in seen:                      # cycle guard
            return 0.0
        kids = children.get(nid, [])
        own = _num_pct(rows[nid].get("pct_complete")) if nid in rows else None
        if not kids:
            v = own if own is not None else 0.0
        else:
            cv = [effective(k, seen + (nid,)) for k in kids]
            rolled = sum(cv) / len(cv) if cv else 0.0
            v = own if (own is not None and own > 0) else rolled   # own entry overrides
        eff_memo[nid] = v
        return v

    def subtree(nid, seen=()):
        cnt = done = 0
        risky = []
        for k in children.get(nid, []):
            if k in seen:
                continue
            cnt += 1
            st = str(rows[k].get("status", ""))
            if st == "Completed":
                done += 1
            if st in RISK_STATUSES:
                risky.append(str(rows[k].get("name", "")))
            cc, cd, cr = subtree(k, seen + (nid,))
            cnt += cc
            done += cd
            risky += cr
        return cnt, done, risky

    recs = []
    for rid in ids:
        kids = children.get(rid, [])
        eff = effective(rid)
        rolled = (sum(effective(k) for k in kids) / len(kids)) if kids else None
        cnt, done, risky = subtree(rid)
        recs.append({
            "task_count": len(kids),
            "tasks_done": done,
            "rollup_pct": round(rolled, 1) if rolled is not None else None,
            "rollup_risk": bool(risky),
            "risk_reason": (", ".join(sorted(set(risky))[:3]) + f" ({len(risky)} of {cnt})") if risky else "",
            "effective_pct": round(eff, 1),
        })
    roll = pd.DataFrame(recs, index=df.index)
    for c in roll.columns:
        df[c] = roll[c].values
    return df


def needs_attention(row) -> bool:
    own = str(row.get("status", "")) in {"Behind", "At Risk", "Blocked"}
    return bool(own or row.get("rollup_risk"))
