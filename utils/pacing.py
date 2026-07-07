"""
utils/pacing.py
Financial pacing engine for BOD-level initiative dashboards.

Pace Score = (Realized / Forecasted) / (Days Elapsed / Total Days)
  ≥ 1.00  → On Pace / Ahead   (green)
  0.75–1.0 → At Risk           (amber)
  < 0.75  → Behind Pace       (red)

Projected EOY = (Realized / Days Elapsed) × Total Days
Gap to Goal   = Forecasted - Projected EOY
"""
from datetime import date, timedelta
from typing import Optional
import pandas as pd


def pace_score(
    realized: Optional[float],
    forecasted: Optional[float],
    start: Optional[date],
    target: Optional[date],
    today: date = None,
) -> Optional[float]:
    """
    Returns pace score (0.0+). None if insufficient data.
    """
    today = today or date.today()
    if not all([realized is not None, forecasted, start, target]):
        return None
    if forecasted == 0:
        return None
    total_days   = (target - start).days
    elapsed_days = (today - start).days
    if total_days <= 0 or elapsed_days <= 0:
        return None
    time_pct  = min(elapsed_days / total_days, 1.0)
    value_pct = realized / forecasted
    return round(value_pct / time_pct, 3) if time_pct > 0 else None


def pace_color(score: Optional[float]) -> str:
    if score is None:     return "#64748B"
    if score >= 1.0:      return "#22C55E"
    if score >= 0.75:     return "#F59E0B"
    return "#EF4444"


def pace_label(score: Optional[float]) -> str:
    if score is None:     return "No Data"
    if score >= 1.0:      return "On Pace"
    if score >= 0.75:     return "At Risk"
    return "Behind"


def pace_icon(score: Optional[float]) -> str:
    if score is None:     return "⚪"
    if score >= 1.0:      return "🟢"
    if score >= 0.75:     return "🟡"
    return "🔴"


def projected_eoy(
    realized: Optional[float],
    start: Optional[date],
    target: Optional[date],
    today: date = None,
) -> Optional[float]:
    """Extrapolate realized value to full project period."""
    today = today or date.today()
    if not all([realized is not None, start, target]):
        return None
    elapsed = (today - start).days
    total   = (target - start).days
    if elapsed <= 0 or total <= 0:
        return None
    return round((realized / elapsed) * total, 2)


def days_remaining(target: Optional[date], today: date = None) -> Optional[int]:
    today = today or date.today()
    if not target:
        return None
    return (target - today).days


def pct_time_elapsed(
    start: Optional[date],
    target: Optional[date],
    today: date = None,
) -> Optional[float]:
    today = today or date.today()
    if not all([start, target]):
        return None
    total   = (target - start).days
    elapsed = (today - start).days
    if total <= 0:
        return None
    return round(min(elapsed / total * 100, 100), 1)


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add pacing columns to a DataFrame of initiatives.
    Works on BOD-level rows with financial data.
    """
    today = date.today()

    def _row_pace(row, field_r, field_f):
        return pace_score(
            row.get(field_r), row.get(field_f),
            row.get("start_date"), row.get("target_completion"), today
        )

    def _row_proj(row, field_r):
        return projected_eoy(
            row.get(field_r), row.get("start_date"),
            row.get("target_completion"), today
        )

    df = df.copy()

    # Revenue pacing
    df["rev_pace_score"]  = df.apply(lambda r: _row_pace(r, "realized_revenue", "forecasted_revenue"), axis=1)
    df["rev_pace_label"]  = df["rev_pace_score"].apply(pace_label)
    df["rev_pace_color"]  = df["rev_pace_score"].apply(pace_color)
    df["rev_projected"]   = df.apply(lambda r: _row_proj(r, "realized_revenue"), axis=1)
    df["rev_gap"]         = df.apply(lambda r:
        (r.get("forecasted_revenue") or 0) - (r["rev_projected"] or 0)
        if r["rev_projected"] is not None else None, axis=1)

    # EBITDA pacing
    df["ebitda_pace_score"] = df.apply(lambda r: _row_pace(r, "realized_ebitda", "forecasted_ebitda"), axis=1)
    df["ebitda_pace_label"] = df["ebitda_pace_score"].apply(pace_label)
    df["ebitda_pace_color"] = df["ebitda_pace_score"].apply(pace_color)
    df["ebitda_projected"]  = df.apply(lambda r: _row_proj(r, "realized_ebitda"), axis=1)
    df["ebitda_gap"]        = df.apply(lambda r:
        (r.get("forecasted_ebitda") or 0) - (r["ebitda_projected"] or 0)
        if r["ebitda_projected"] is not None else None, axis=1)

    # Time pacing
    df["pct_time_elapsed"] = df.apply(
        lambda r: pct_time_elapsed(r.get("start_date"), r.get("target_completion"), today), axis=1
    )
    df["days_remaining"]   = df.apply(
        lambda r: days_remaining(r.get("target_completion"), today), axis=1
    )

    return df


def summary_stats(df: pd.DataFrame) -> dict:
    """Aggregate financial stats across a set of initiatives."""
    today = date.today()
    bod   = df[df.get("category", pd.Series(dtype=str)) == "BOD"] if "category" in df.columns else df

    total_forecasted_rev    = bod["forecasted_revenue"].sum(skipna=True)
    total_realized_rev      = bod["realized_revenue"].sum(skipna=True)
    total_forecasted_ebitda = bod["forecasted_ebitda"].sum(skipna=True)
    total_realized_ebitda   = bod["realized_ebitda"].sum(skipna=True)

    on_track  = (bod["status"] == "On Track").sum()  if "status" in bod.columns else 0
    at_risk   = (bod["status"] == "At Risk").sum()   if "status" in bod.columns else 0
    behind    = (bod["status"] == "Behind").sum()    if "status" in bod.columns else 0
    blocked   = (bod["status"] == "Blocked").sum()   if "status" in bod.columns else 0
    completed = (bod["status"] == "Completed").sum() if "status" in bod.columns else 0
    total     = len(bod)

    return {
        "total":                  total,
        "on_track":               int(on_track),
        "at_risk":                int(at_risk),
        "behind":                 int(behind),
        "blocked":                int(blocked),
        "completed":              int(completed),
        "total_forecasted_rev":   total_forecasted_rev,
        "total_realized_rev":     total_realized_rev,
        "total_forecasted_ebitda":total_forecasted_ebitda,
        "total_realized_ebitda":  total_realized_ebitda,
        "rev_pct":    round(total_realized_rev / total_forecasted_rev * 100, 1) if total_forecasted_rev else 0,
        "ebitda_pct": round(total_realized_ebitda / total_forecasted_ebitda * 100, 1) if total_forecasted_ebitda else 0,
    }
