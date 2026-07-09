"""
components/financial_charts.py  —  DemandPulse color scheme.
"""
import plotly.graph_objects as go
import pandas as pd
from datetime import date
import math

CARD_BG = "#ffffff"
GRID    = "#cddde7"
NAVY    = "#0d2535"
NAVY2   = "#294c60"
TEAL    = "#557888"
BORDER  = "#aac4d4"

STATUS_COLORS = {
    "On Track":    "#5a8010",
    "At Risk":     "#d97706",
    "Behind":      "#dc2626",
    "Blocked":     "#7c3aed",
    "Completed":   "#0369a1",
    "Not Started": "#aac4d4",
}


def _v(val):
    """Safe float — returns 0.0 for None/NaN."""
    if val is None: return 0.0
    try:
        f = float(val)
        return 0.0 if math.isnan(f) else f
    except: return 0.0


def _pace_color(score):
    if score is None: return "#aac4d4"
    if score >= 1.0:  return "#5a8010"
    if score >= 0.75: return "#d97706"
    return "#dc2626"


def _base_layout(title="", height=380, left_margin=240):
    return dict(
        title=dict(text=title, font=dict(color=NAVY, size=13, family="Syne, sans-serif")),
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font=dict(color=NAVY2, size=11, family="Inter, sans-serif"),
        height=height,
        margin=dict(l=left_margin, r=20, t=45, b=40),
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=BORDER, tickcolor=BORDER),
        yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=BORDER, tickcolor=BORDER),
        legend=dict(bgcolor=CARD_BG, bordercolor=GRID, font=dict(color=NAVY2),
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )


def _horiz_bar(df, fcst_col, real_col, pace_col, title):
    sub = df[df[fcst_col].notna() & (df[fcst_col] > 0)].copy()
    if sub.empty:
        return _empty_fig(f"No {title.split(':')[0].strip()} forecast data available")
    sub    = sub.sort_values(fcst_col, ascending=True)
    labels = sub["name"].apply(lambda x: x[:45]+"…" if len(x)>45 else x)
    scores = sub.get(pace_col, pd.Series([None]*len(sub), index=sub.index))
    fig    = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=sub[fcst_col], name="Forecasted", orientation="h",
                         marker_color="#cddde7",
                         hovertemplate="<b>%{y}</b><br>Forecasted: $%{x:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(y=labels, x=sub[real_col].fillna(0), name="Realized", orientation="h",
                         marker_color=[_pace_color(s) for s in scores],
                         hovertemplate="<b>%{y}</b><br>Realized: $%{x:,.0f}<extra></extra>"))
    h = max(320, len(sub)*22+100)
    layout = _base_layout(title, height=h)
    layout["xaxis"]["tickprefix"] = "$"
    layout["xaxis"]["tickformat"] = ",.0f"
    fig.update_layout(**layout, barmode="overlay")
    return fig


# ── Public chart functions ─────────────────────────────────────────────────

def status_donut(df: pd.DataFrame) -> go.Figure:
    order  = ["On Track","At Risk","Behind","Blocked","Not Started","Completed"]
    counts = df["status"].value_counts().reindex(order).fillna(0)
    colors = [STATUS_COLORS.get(s, TEAL) for s in counts.index]
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.65,
        marker=dict(colors=colors, line=dict(color=CARD_BG, width=2)),
        textinfo="label+value", textfont=dict(color=NAVY2, size=11),
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    fig.update_layout(**_base_layout("Initiative Status", height=320))
    fig.update_layout(showlegend=False, margin=dict(l=10,r=10,t=45,b=10))
    return fig


def ebitda_pacing_bar(df: pd.DataFrame) -> go.Figure:
    return _horiz_bar(df, "forecasted_ebitda", "realized_ebitda",
                      "ebitda_pace_score", "EBITDA Impact: Forecasted vs Realized")


def revenue_pacing_bar(df: pd.DataFrame) -> go.Figure:
    return _horiz_bar(df, "forecasted_revenue", "realized_revenue",
                      "rev_pace_score", "Revenue Impact: Forecasted vs Realized")


def cost_pacing_bar(df: pd.DataFrame) -> go.Figure:
    sub = df[df["forecasted_cost"].notna() & (df["forecasted_cost"] > 0)].copy()
    if sub.empty:
        return _empty_fig("No forecasted cost data available")
    sub    = sub.sort_values("forecasted_cost", ascending=True)
    labels = sub["name"].apply(lambda x: x[:45]+"…" if len(x)>45 else x)
    def _cost_color(row):
        f = _v(row.get("forecasted_cost")); r = _v(row.get("realized_cost"))
        if f == 0: return "#aac4d4"
        ratio = r / f
        if ratio <= 0.75: return "#5a8010"
        if ratio <= 1.0:  return "#d97706"
        return "#dc2626"
    fig = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=sub["forecasted_cost"], name="Budgeted",
                         orientation="h", marker_color="#cddde7",
                         hovertemplate="<b>%{y}</b><br>Budgeted: $%{x:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(y=labels, x=sub["realized_cost"].fillna(0), name="Actual",
                         orientation="h",
                         marker_color=[_cost_color(row) for _, row in sub.iterrows()],
                         hovertemplate="<b>%{y}</b><br>Actual: $%{x:,.0f}<extra></extra>"))
    h = max(320, len(sub)*22+100)
    layout = _base_layout("Project Cost: Budgeted vs Actual", height=h)
    layout["xaxis"]["tickprefix"] = "$"
    layout["xaxis"]["tickformat"] = ",.0f"
    fig.update_layout(**layout, barmode="overlay")
    return fig


def ebitda_cumulative_curve(df: pd.DataFrame) -> go.Figure:
    """
    Cumulative EBITDA curve: expected ramp vs actual realized.
    Expected line = sum of each initiative's proportional contribution at each month end.
    Shows exactly how far ahead/behind the portfolio is vs the expected pace.
    """
    today   = date.today()
    yr      = today.year
    months  = pd.date_range(f"{yr}-01-01", f"{yr}-12-31", freq="ME")

    bod = df[
        df["forecasted_ebitda"].notna() &
        (df["forecasted_ebitda"] > 0) &
        df["start_date"].notna() &
        df["target_completion"].notna()
    ].copy()

    if bod.empty:
        return _empty_fig("No EBITDA data with project dates available")

    expected_vals = []
    for m in months:
        m_date = m.date()
        total  = 0.0
        for _, row in bod.iterrows():
            s = row["start_date"]; t = row["target_completion"]; f = _v(row["forecasted_ebitda"])
            total_days = (t - s).days
            if total_days <= 0: continue
            elapsed = max(0, min((m_date - s).days, total_days))
            total  += f * (elapsed / total_days)
        expected_vals.append(round(total))

    total_realized  = sum(_v(r) for r in bod["realized_ebitda"])
    today_month_idx = min(today.month - 1, len(expected_vals) - 1)
    expected_today  = expected_vals[today_month_idx]
    gap             = total_realized - expected_today

    month_labels = [m.strftime("%b") for m in months]

    fig = go.Figure()

    # Expected ramp line
    fig.add_trace(go.Scatter(
        x=month_labels, y=expected_vals,
        mode="lines+markers", name="Expected Cumulative",
        line=dict(color="#aac4d4", width=2, dash="dash"),
        marker=dict(size=5, color="#aac4d4"),
        hovertemplate="<b>%{x}</b><br>Expected: $%{y:,.0f}<extra></extra>",
    ))

    # Actual realized — flat line up to today
    actual_y = [total_realized if m.date() <= today else None for m in months]
    fig.add_trace(go.Scatter(
        x=month_labels, y=actual_y,
        mode="lines+markers", name="Realized To Date",
        line=dict(color="#5a8010" if gap >= 0 else "#dc2626", width=3),
        marker=dict(size=7, color="#5a8010" if gap >= 0 else "#dc2626"),
        hovertemplate="<b>%{x}</b><br>Realized: $%{y:,.0f}<extra></extra>",
        connectgaps=False,
    ))

    # Gap annotation at today
    gap_color = "#5a8010" if gap >= 0 else "#dc2626"
    gap_label = f"{'▲' if gap>=0 else '▼'} ${abs(gap):,.0f} {'ahead' if gap>=0 else 'behind'}"
    fig.add_annotation(
        x=month_labels[today_month_idx],
        y=total_realized,
        text=gap_label,
        showarrow=True, arrowhead=2, arrowcolor=gap_color,
        font=dict(color=gap_color, size=12, family="Syne, sans-serif"),
        bgcolor=CARD_BG, bordercolor=gap_color, borderwidth=1,
        ay=-40, ax=20,
    )

    # Today vertical line — use add_shape for categorical x-axis (add_vline needs numeric)
    fig.add_shape(
        type="line",
        x0=today_month_idx, x1=today_month_idx,
        y0=0, y1=1,
        xref="x", yref="paper",
        line=dict(color="#d97706", dash="dot", width=1.5),
    )
    fig.add_annotation(
        x=month_labels[today_month_idx], y=1, yref="paper",
        text="Today", showarrow=False,
        font=dict(color="#d97706", size=10),
        yanchor="bottom", bgcolor="rgba(255,255,255,0.7)",
    )

    layout = _base_layout("EBITDA: Expected Pace vs Realized (Cumulative)", height=380)
    layout["margin"]  = dict(l=70, r=20, t=45, b=40)
    layout["yaxis"]["tickprefix"] = "$"
    layout["yaxis"]["tickformat"] = ",.0f"
    fig.update_layout(**layout)
    return fig


def ebitda_gap_bar(df: pd.DataFrame) -> go.Figure:
    """
    Gap-to-expected bar: one bar per initiative = Realized - Expected Today.
    Green = ahead of pace, Red = behind pace. Sorted worst first.
    Immediately shows which initiatives are dragging the portfolio.
    """
    today = date.today()
    rows  = []

    for _, row in df.iterrows():
        f = _v(row.get("forecasted_ebitda"))
        r = _v(row.get("realized_ebitda"))
        s = row.get("start_date")
        t = row.get("target_completion")
        if f <= 0 or not s or not t: continue
        total_days = (t - s).days
        if total_days <= 0: continue
        elapsed      = max(0, min((today - s).days, total_days))
        exp_today    = f * (elapsed / total_days)
        gap          = r - exp_today
        name         = row.get("name","")
        rows.append({"name": name, "gap": gap, "realized": r,
                     "expected": exp_today, "status": row.get("status","")})

    if not rows:
        return _empty_fig("Insufficient data for gap analysis")

    gdf = pd.DataFrame(rows).sort_values("gap", ascending=True)
    labels = gdf["name"].apply(lambda x: x[:45]+"…" if len(x)>45 else x)
    colors = ["#5a8010" if g >= 0 else "#dc2626" for g in gdf["gap"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=gdf["gap"],
        orientation="h",
        marker_color=colors,
        marker_line_color=CARD_BG, marker_line_width=0.5,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Gap: $%{x:,.0f}<br>"
            "Realized: $%{customdata[0]:,.0f}<br>"
            "Expected today: $%{customdata[1]:,.0f}<extra></extra>"
        ),
        customdata=list(zip(gdf["realized"].round(), gdf["expected"].round())),
        name="",
    ))

    # Zero reference line
    fig.add_vline(x=0, line_color=NAVY2, line_width=1.5)

    h = max(380, len(gdf)*22+100)
    layout = _base_layout("EBITDA Gap to Expected Pace (as of today)", height=h)
    layout["xaxis"]["tickprefix"] = "$"
    layout["xaxis"]["tickformat"] = ",.0f"
    layout["xaxis"]["title"]      = "← Behind Expected Pace    |    Ahead of Expected Pace →"
    fig.update_layout(**layout, showlegend=False)
    return fig


def _as_date(v):
    """Coerce a value to a date (handles date/datetime, ISO strings, US formats).
    Returns None if it isn't a usable date - so mixed str/date columns can't crash
    the sort/arithmetic below."""
    from datetime import date as _date, datetime as _dt
    if isinstance(v, _dt):
        return v.date()
    if isinstance(v, _date):
        return v
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    if "T" in s:
        s = s.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return _dt.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _pace_health(row, today):
    """(color, label, progress_fraction) for a timeline bar, judged on PACE, not
    the manually-set status. Progress = realized EBITDA vs budget for EBITDA
    projects, else % complete; pace = progress vs the fraction of the schedule
    elapsed. Green = on/ahead, amber = a bit behind, red = well behind."""
    sd, td = row["_sd"], row["_td"]
    total = max((td - sd).days, 1)
    elapsed = min(max((today - sd).days, 0), total)
    exp = elapsed / total                                  # where they should be
    fe = _v(row.get("forecasted_ebitda"))
    if fe > 0:
        prog = _v(row.get("realized_ebitda")) / fe
        detail = f"EBITDA ${_v(row.get('realized_ebitda')):,.0f} / ${fe:,.0f} = {prog*100:.0f}%"
    else:
        prog = _v(row.get("pct_complete")) / 100.0
        detail = f"{_v(row.get('pct_complete')):.0f}% complete"
    if str(row.get("status", "")) == "Completed" or prog >= 1.0:
        return "#0369a1", "Complete", min(prog, 1.0), detail
    pace = (prog / exp) if exp > 0 else None
    if pace is None:
        return "#94a3b8", "Not started", prog, detail
    if pace >= 0.9:
        return "#2f8f3e", "On pace", prog, detail
    if pace >= 0.7:
        return "#f1a500", "At risk", prog, detail
    return "#cc4749", "Behind", prog, detail


def completion_timeline(df: pd.DataFrame) -> go.Figure:
    sub = df.copy()
    sub["_sd"] = sub["start_date"].apply(_as_date)
    sub["_td"] = sub["target_completion"].apply(_as_date)
    sub = sub[sub["_sd"].notna() & sub["_td"].notna()].copy()
    if sub.empty:
        return _empty_fig("No date data available")
    sub   = sub.sort_values("_sd")          # all matching rows, earliest start first
    today = date.today()

    labels, offsets, durs, prog_x, colors, hovers = [], [], [], [], [], []
    seen = {}
    for _, row in sub.iterrows():
        nm = row.get("name", "") or "(unnamed)"
        label = (nm[:40] + "…") if len(nm) > 40 else nm
        seen[label] = seen.get(label, 0) + 1
        if seen[label] > 1:                                # keep y-categories unique
            label = f"{label} ({seen[label]})"
        col, plabel, prog, detail = _pace_health(row, today)
        offset = (row["_sd"] - date(today.year, 1, 1)).days
        dur = (row["_td"] - row["_sd"]).days
        labels.append(label); offsets.append(offset); durs.append(dur)
        prog_x.append(dur * min(max(prog, 0.0), 1.0)); colors.append(col)
        hovers.append(f"<b>{label}</b><br>Pace: {plabel}<br>{detail}<br>"
                      f"{row['_sd']} → {row['_td']}<extra></extra>")

    fig = go.Figure()
    # Full schedule (light track)
    fig.add_trace(go.Bar(y=labels, x=durs, base=offsets, orientation="h",
                         marker_color="#e8eff4", marker_line_color=CARD_BG,
                         marker_line_width=1, showlegend=False, hoverinfo="skip"))
    # Progress fill, colored by pace
    fig.add_trace(go.Bar(y=labels, x=prog_x, base=offsets, orientation="h",
                         marker_color=colors, showlegend=False,
                         hovertemplate=hovers))
    today_offset = (today - date(today.year, 1, 1)).days
    fig.add_vline(x=today_offset, line_color="#d97706", line_width=1.5, line_dash="dot",
                  annotation_text="Today", annotation_font_color="#d97706", annotation_font_size=10)
    h = max(400, len(sub) * 22 + 80)
    layout = _base_layout("Initiative Timeline - colored by pace (progress vs schedule)", height=h)
    layout["xaxis"].update(
        title="", tickvals=[0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334],
        ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    )
    layout["margin"] = dict(l=280, r=20, t=45, b=40)
    fig.update_layout(**layout, barmode="overlay", showlegend=False)
    return fig


def _empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font=dict(color=TEAL, size=13))
    fig.update_layout(**_base_layout(height=200))
    return fig
