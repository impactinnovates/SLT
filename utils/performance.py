"""
utils/performance.py
EBITDA performance rating for the thumb gauge.

The rating is pace-aware: at mid-year you should have realized roughly the
fraction of the year that has elapsed, so we compare realized against
"expected by now" (forecast x year-fraction), not against the full-year forecast.

  thumb = up    (green)  pace >= 1.00   at or ahead of where we should be
          side  (amber)  0.70-1.00      at risk, tracking a bit behind
          down  (red)    < 0.70         far below forecast pace
A group with no budget but realized savings is pure upside -> up.
Thresholds live here so they're easy to tune.
"""
from datetime import date

ON, AT, BEHIND = 1.00, 0.70, 0.0


def year_fraction(today: date | None = None) -> float:
    today = today or date.today()
    start = date(today.year, 1, 1)
    end = date(today.year, 12, 31)
    total = (end - start).days + 1
    return min(max((today - start).days / total, 0.0), 1.0)


def _num(v):
    try:
        f = float(v)
        return 0.0 if f != f else f
    except (TypeError, ValueError):
        return 0.0


def rate(realized: float, forecast: float, yf: float) -> dict:
    """Return dict with thumb, pace, attainment for one realized/forecast pair."""
    realized, forecast = _num(realized), _num(forecast)
    if forecast <= 0:
        # No budget target: any realized savings is all upside.
        thumb = "up" if realized > 0 else "none"
        return {"thumb": thumb, "pace": None, "attainment": None,
                "realized": realized, "forecast": forecast}
    attainment = realized / forecast
    expected = forecast * yf
    pace = realized / expected if expected > 0 else None
    if pace is None:
        thumb = "none"
    elif pace >= ON:
        thumb = "up"
    elif pace >= AT:
        thumb = "side"
    else:
        thumb = "down"
    return {"thumb": thumb, "pace": pace, "attainment": attainment,
            "realized": realized, "forecast": forecast}


def summarize(df, yf: float) -> dict:
    r = df["realized_ebitda"].apply(_num).sum() if "realized_ebitda" in df else 0.0
    f = df["forecasted_ebitda"].apply(_num).sum() if "forecasted_ebitda" in df else 0.0
    out = rate(r, f, yf)
    out["n"] = len(df)
    return out


_ORDER = {"down": 0, "side": 1, "up": 2, "none": 3}


def by_dimension(df, dim: str, yf: float) -> list:
    """One EBITDA-rated summary per group in `dim`, worst pace first."""
    if dim not in df.columns:
        return []
    keys = df[dim].replace("", "(unassigned)").fillna("(unassigned)")
    groups = []
    for val, g in df.groupby(keys):
        s = summarize(g, yf)
        s["label"] = str(val)
        groups.append(s)
    return sorted(groups, key=lambda x: (_ORDER.get(x["thumb"], 9),
                                         x["pace"] if x["pace"] is not None else 99))


# ── Progress-by-volume gauge (the mirror thumb) ─────────────────────────────
# Rates execution across the COUNT of projects, not dollars: average % complete
# vs the fraction of the year elapsed. Includes projects with no EBITDA impact,
# so you can tell whether work is moving even when the financial number lags.
def progress_summary(df, yf: float) -> dict:
    if df.empty:
        return {"thumb": "none", "avg_pct": None, "pace": None,
                "expected_pct": round(yf * 100), "n": 0}
    avg = float(df["pct_complete"].apply(_num).mean()) if "pct_complete" in df else 0.0
    expected = yf * 100
    pace = avg / expected if expected > 0 else None
    if pace is None:
        thumb = "none"
    elif pace >= ON:
        thumb = "up"
    elif pace >= AT:
        thumb = "side"
    else:
        thumb = "down"
    return {"thumb": thumb, "avg_pct": avg, "pace": pace,
            "expected_pct": round(expected), "n": len(df)}


def progress_by_dimension(df, dim: str, yf: float) -> list:
    if dim not in df.columns:
        return []
    keys = df[dim].replace("", "(unassigned)").fillna("(unassigned)")
    groups = []
    for val, g in df.groupby(keys):
        s = progress_summary(g, yf)
        s["label"] = str(val)
        groups.append(s)
    return sorted(groups, key=lambda x: (_ORDER.get(x["thumb"], 9),
                                         x["pace"] if x["pace"] is not None else 99))
