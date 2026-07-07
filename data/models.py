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

# SharePoint Graph field names → internal
GRAPH_MAP = {
    "Title":                     "name",
    "Sponsor":                   "sponsor",
    "Owner":                     "owner",
    "Region":                    "region",
    "Category":                  "category",
    "Priority":                  "priority",
    "Description":               "description",
    "Status":                    "status",
    "PercentComplete":           "pct_complete",
    "CompletedActions":          "completed_actions",
    "NextAction":                "next_action",
    "Blockers":                  "blockers",
    "StartDate":                 "start_date",
    "TargetCompletion":          "target_completion",
    "RevisedCompletion":         "revised_completion",
    "ActualCompletion":          "actual_completion",
    "ForecastedCost":            "forecasted_cost",
    "RealizedCost":              "realized_cost",
    "ForecastedRevenueImpact":   "forecasted_revenue",
    "RealizedRevenueToDate":     "realized_revenue",
    "ForecastedEBITDAImpact":    "forecasted_ebitda",
    "RealizedEBITDAToDate":      "realized_ebitda",
    "BenefitStartDate":          "benefit_start_date",
    "ProjectLink":               "project_link",
    "ParentID":                  "parent_id",   # reconcile internal name via probe
    "TaskInitiative":            "task_type",    # reconcile internal name via probe
    "id":                        "sp_id",   # SharePoint item ID for write-back
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
