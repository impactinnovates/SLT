"""
data/models.py
Data models and field name normalization.
Maps both CSV column names and SharePoint Graph field names to
a consistent internal schema.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# ── Column mapping: CSV header → internal field name ─────────────────────
CSV_MAP = {
    "\ufeff\"Task/Initiative\"": "task_type",
    "Task/Initiative":           "task_type",
    "Sponsor":                   "sponsor",
    "Owner":                     "owner",
    "Region":                    "region",
    "Category":                  "category",
    "Priority":                  "priority",
    "Initiative Name":           "name",
    "Description":               "description",
    "Status":                    "status",
    "% Complete":                "pct_complete",
    "Completed Actions":         "completed_actions",
    "Next Action":               "next_action",
    "Blockers":                  "blockers",
    "Start Date":                "start_date",
    "Target Completion":         "target_completion",
    "Revised Completion":        "revised_completion",
    "Actual Completion":         "actual_completion",
    "Forecasted Cost":           "forecasted_cost",
    "Realized Cost":             "realized_cost",
    "Forecasted Revenue Impact": "forecasted_revenue",
    "Realized Revenue To Date":  "realized_revenue",
    "Forecasted EBITDA Impact":  "forecasted_ebitda",
    "Realized EBITDA To Date":   "realized_ebitda",
    "Benefit Start Date":        "benefit_start_date",
    "Project Link":              "project_link",
    "Last Updated By":           "last_updated_by",
    "Approval status":           "approval_status",
    "ID":                        "id",
    "Created By":                "created_by",
    "Modified By":               "modified_by",
    "Parent ID":                 "parent_id",
}

# Row type (the List's "Task/Initiative" field -> task_type). Initiatives are the
# SLT-owned parents; Tasks are children assigned to Leaders and roll up to a parent
# via parent_id.
TYPE_INITIATIVE = "Initiative"
TYPE_TASK       = "Task"

# SharePoint Graph field names → internal.
# Reconciled against the live List via probe_list_connection.py (2026-07-08).
# The List uses SharePoint's auto-generated internal names (field_N and encoded
# names), NOT friendly ones — do NOT "tidy" these keys, they must match the
# List's internal column names exactly. Gaps in the field_N sequence (11, 17,
# 25-27) are columns that were deleted in SharePoint.
GRAPH_MAP = {
    "Title":                  "name",           # display: Initiative Name (Title)
    "Task_x002f_Initiative":  "task_type",      # display: Task/Initiative
    "field_1":                "category",
    "field_2":                "owner",
    "field_3":                "sponsor",
    "field_4":                "priority",
    "field_5":                "region",
    "field_6":                "description",
    "field_7":                "status",
    "field_8":                "pct_complete",
    "field_9":                "completed_actions",
    "field_10":               "next_action",
    "field_12":               "blockers",
    "field_13":               "start_date",
    "field_14":               "target_completion",
    "field_15":               "revised_completion",
    "field_16":               "actual_completion",
    "field_18":               "forecasted_cost",
    "field_19":               "realized_cost",
    "field_20":               "forecasted_revenue",
    "field_21":               "realized_revenue",
    "field_22":               "forecasted_ebitda",
    "field_23":               "realized_ebitda",
    "field_24":               "benefit_start_date",
    "field_28":               "last_updated_by",
    "ProjectLink":            "project_link",
    "ParentID":               "parent_id",
    # NOTE: deliberately NOT mapping "id" -> "sp_id". source._from_graph already
    # sets sp_id from _sp_item_id; mapping "id" here too produced a DUPLICATE
    # "sp_id" column (a DataFrame, not a Series) that crashed _clean_df.
}

# Reverse map for writing back to SharePoint
INTERNAL_TO_GRAPH = {v: k for k, v in GRAPH_MAP.items() if k != "id"}

STATUS_COLORS = {
    "On Track":    "#22C55E",
    "At Risk":     "#F59E0B",
    "Behind":      "#EF4444",
    "Blocked":     "#8B5CF6",
    "Completed":   "#3B82F6",
    "Not Started": "#64748B",
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
    "1": "#EF4444",
    "2": "#F59E0B",
    "3": "#22C55E",
}

CATEGORY_LABELS = {
    "BOD": "Board / SLT",
    "SM":  "Site Manufacturing",
}


def parse_currency(val: str) -> Optional[float]:
    """Parse '$1,234,567' or '1234567' → float. Returns None if empty."""
    if not val or str(val).strip() in ("", "0", "$0"):
        return None
    cleaned = str(val).replace("$", "").replace(",", "").strip()
    try:
        v = float(cleaned)
        return v if v != 0 else None
    except ValueError:
        return None


def parse_pct(val: str) -> Optional[float]:
    """Parse '75%' or '0.75' → float 0–100."""
    if not val or str(val).strip() == "":
        return None
    cleaned = str(val).replace("%", "").strip()
    try:
        v = float(cleaned)
        return v if v <= 1 else v   # handle both 0.75 and 75
    except ValueError:
        return None


def parse_date(val: str) -> Optional[date]:
    if not val or str(val).strip() == "0" or str(val).strip() == "":
        return None
    from datetime import datetime
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None
