"""
app.py - IEG Strategic Initiatives (Flask + Jinja2 + HTMX).

Replaces the early Streamlit build. Same shape as DemandPulse/SCP:
  - Microsoft Entra SSO (auth.py); runs open locally as a dev SLT user.
  - Role layers from config/roles.yaml: SLT (all + financials), PM (Site
    Manufacturing, no financials), TM (their assigned sub-tasks only).
  - Data via data/loader.py -> data/source.py: live SharePoint List when the
    GRAPH_* credentials are configured, otherwise the local CSV export.

Run (dev):   python app.py                 -> http://127.0.0.1:8502
Run (prod):  gunicorn -b 0.0.0.0:8502 wsgi:app
"""
from datetime import timedelta, date, datetime

import pandas as pd
from flask import (Flask, render_template, request, redirect, url_for,
                   session, g, abort, jsonify)

from config import settings
import auth
from data.loader import (load_initiatives, update_initiative, create_initiative,
                         delete_initiative, load_sub_initiatives, save_sub_initiatives,
                         clear_cache)
from data import source
from data.models import STATUS_COLORS, STATUS_ICONS
from utils.pacing import enrich_dataframe, summary_stats
from components import financial_charts as fc

app = Flask(__name__)
app.secret_key = settings.SESSION_SECRET or "dev-only-insecure-key-change-me"
app.permanent_session_lifetime = timedelta(hours=8)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=bool(settings.ENTRA_CLIENT_ID))

app.register_blueprint(auth.bp)
app.before_request(auth.require_login)

STATUSES = ["On Track", "At Risk", "Behind", "Blocked", "Not Started", "Completed"]


# ── Jinja helpers ───────────────────────────────────────────────────────────
@app.template_filter("currency")
def _currency(val):
    if val is None or (isinstance(val, float) and val != val):
        return "-"
    try:
        return f"${float(val):,.0f}"
    except (TypeError, ValueError):
        return "-"


@app.template_filter("pct")
def _pct(val):
    if val is None or (isinstance(val, float) and val != val):
        return "-"
    return f"{float(val):.0f}%"


@app.template_filter("date")
def _date(val):
    if val is None or (isinstance(val, float) and val != val) or val == "":
        return "-"
    if isinstance(val, (date, datetime)):
        return val.strftime("%b %d, %Y")
    return str(val)


@app.context_processor
def _inject():
    return {
        "user": getattr(g, "user", None),
        "source_label": source.source_label(),
        "status_colors": STATUS_COLORS,
        "status_icons": STATUS_ICONS,
    }


# ── Data prep ───────────────────────────────────────────────────────────────
def _scoped_df() -> pd.DataFrame:
    """Enriched initiatives, scoped to the signed-in user's role."""
    df = enrich_dataframe(load_initiatives())
    role = g.user["role"]
    if role == "SLT":
        return df
    if role == "PM":
        # Site Manufacturing only; financials are hidden in the templates.
        return df[df.get("category", "") == "SM"].copy() if "category" in df.columns else df
    return df.iloc[0:0]  # TM: no top-level initiatives, only sub-tasks


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Query-param filters (multi-select via repeated params); OR for
    sponsor/owner, AND for the rest, matching the old global filter bar."""
    if df.empty:
        return df
    a = request.args
    spon = a.getlist("sponsor")
    own = a.getlist("owner")
    mask = pd.Series([True] * len(df), index=df.index)
    if spon or own:
        sm = df["sponsor"].isin(spon) if spon else pd.Series([False] * len(df), index=df.index)
        om = df["owner"].isin(own) if own else pd.Series([False] * len(df), index=df.index)
        mask &= (sm | om)
    for col in ("status", "region", "category"):
        vals = a.getlist(col)
        if vals and col in df.columns:
            mask &= df[col].isin(vals)
    if a.get("show_completed", "1") not in ("1", "true", "on") and "status" in df.columns:
        mask &= df["status"] != "Completed"
    return df[mask].copy()


def _filter_options(df: pd.DataFrame) -> dict:
    def uniq(col):
        return sorted(df[col].dropna().unique().tolist()) if col in df.columns else []
    return {"sponsors": uniq("sponsor"), "owners": uniq("owner"),
            "statuses": uniq("status"), "regions": uniq("region"),
            "categories": uniq("category")}


def _fig(fig):
    return fig.to_json()


# ── Routes: landing + role redirect ─────────────────────────────────────────
@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/")
def home():
    role = g.user["role"]
    return redirect({"SLT": "/dashboard", "PM": "/pm/initiatives"}.get(role, "/tm/tasks"))


# ── SLT views ───────────────────────────────────────────────────────────────
@app.route("/dashboard")
@auth.require_role("SLT")
def dashboard():
    df = _apply_filters(_scoped_df())
    bod = df[df["category"] == "BOD"].copy() if "category" in df.columns else df
    stats = summary_stats(df)
    attention = bod[bod["status"].isin(["Behind", "At Risk", "Blocked"])].copy()
    sev = {"Behind": 0, "Blocked": 1, "At Risk": 2}
    attention["_sev"] = attention["status"].map(sev).fillna(9)
    attention = attention.sort_values(["_sev", "name"])
    recent = bod[bod["last_updated_by"].astype(str).str.strip().ne("")].head(8) \
        if "last_updated_by" in bod.columns else bod.iloc[0:0]
    charts = {
        "donut": _fig(fc.status_donut(bod)),
        "ebitda": _fig(fc.ebitda_pacing_bar(bod)),
        "revenue": _fig(fc.revenue_pacing_bar(bod)),
        "cost": _fig(fc.cost_pacing_bar(bod)),
    }
    return render_template("dashboard.html", nav="dashboard", stats=stats,
                           attention=attention.to_dict("records"),
                           recent=recent.to_dict("records"), charts=charts,
                           options=_filter_options(_scoped_df()), args=request.args)


@app.route("/initiatives")
@auth.require_role("SLT")
def initiatives():
    df = _apply_filters(_scoped_df())
    total = len(_scoped_df())
    sort = request.args.get("sort", "pri_sev")
    groups = []
    for cat, label in [("BOD", "Board / SLT Level"), ("SM", "Site Manufacturing")]:
        sub = df[df["category"] == cat].copy() if "category" in df.columns else df.copy()
        if sub.empty:
            continue
        sub = _sort_df(sub, sort)
        groups.append({"label": label, "rows": sub.to_dict("records"), "count": len(sub)})
    return render_template("initiatives.html", nav="initiatives", groups=groups,
                           shown=len(df), total=total, sort=sort,
                           options=_filter_options(_scoped_df()), args=request.args)


def _sort_df(sub: pd.DataFrame, sort: str) -> pd.DataFrame:
    sev = {"Behind": 0, "Blocked": 1, "At Risk": 2, "Not Started": 3, "On Track": 4, "Completed": 5}
    if sort == "pri_sev":
        sub["_sev"] = sub["status"].map(sev).fillna(9)
        sub["_pri"] = pd.to_numeric(sub.get("priority"), errors="coerce").fillna(9)
        return sub.sort_values(["_pri", "_sev", "name"])
    if sort in sub.columns:
        asc = sort != "pct_complete"
        return sub.sort_values(sort, ascending=asc, na_position="last")
    return sub


@app.route("/financial")
@auth.require_role("SLT")
def financial():
    df = _apply_filters(_scoped_df())
    bod = df[df["category"] == "BOD"].copy() if "category" in df.columns else df
    er = bod[bod["forecasted_ebitda"].notna()].copy()
    pace = {
        "on": int((er["ebitda_pace_score"] >= 1.0).sum()) if not er.empty else 0,
        "at": int(((er["ebitda_pace_score"] >= 0.75) & (er["ebitda_pace_score"] < 1.0)).sum()) if not er.empty else 0,
        "behind": int((er["ebitda_pace_score"] < 0.75).sum()) if not er.empty else 0,
        "nodata": int(er["ebitda_pace_score"].isna().sum()) if not er.empty else 0,
    }
    charts = {
        "curve": _fig(fc.ebitda_cumulative_curve(bod)),
        "gap": _fig(fc.ebitda_gap_bar(bod)),
        "ebitda": _fig(fc.ebitda_pacing_bar(er if not er.empty else bod)),
        "revenue": _fig(fc.revenue_pacing_bar(bod)),
        "cost": _fig(fc.cost_pacing_bar(bod)),
    }
    return render_template("financial.html", nav="financial", pace=pace, charts=charts,
                           rows=bod.to_dict("records"),
                           options=_filter_options(_scoped_df()), args=request.args)


@app.route("/timeline")
@auth.require_role("SLT")
def timeline():
    df = _apply_filters(_scoped_df())
    return render_template("timeline.html", nav="timeline",
                           chart=_fig(fc.completion_timeline(df)),
                           options=_filter_options(_scoped_df()), args=request.args)


@app.route("/new")
@auth.require_role("SLT")
def new_initiative():
    return render_template("new.html", nav="new", statuses=STATUSES)


# ── PM views ────────────────────────────────────────────────────────────────
@app.route("/pm/initiatives")
@auth.require_role("SLT", "PM")
def pm_initiatives():
    df = _apply_filters(_scoped_df())
    df = _sort_df(df, request.args.get("sort", "pri_sev"))
    return render_template("pm_initiatives.html", nav="pm_initiatives",
                           rows=df.to_dict("records"), shown=len(df),
                           options=_filter_options(_scoped_df()), args=request.args)


@app.route("/pm/subtasks")
@auth.require_role("SLT", "PM")
def pm_subtasks():
    subs = load_sub_initiatives()
    df = _scoped_df()
    parents = df[["id", "name"]].to_dict("records") if not df.empty else []
    return render_template("pm_subtasks.html", nav="pm_subtasks",
                           subs=subs.to_dict("records"), parents=parents)


# ── TM view ─────────────────────────────────────────────────────────────────
@app.route("/tm/tasks")
def tm_tasks():
    user = g.user
    subs = load_sub_initiatives()
    mine = subs[subs["owner"] == user["name"]] if not subs.empty and "owner" in subs.columns else subs.iloc[0:0]
    return render_template("tm_tasks.html", nav="tm_tasks", tasks=mine.to_dict("records"))


# ── HTMX write endpoints ────────────────────────────────────────────────────
def _editable_from_form(f) -> dict:
    from data.models import parse_currency
    out = {
        "name": f.get("name", "").strip(),
        "status": f.get("status", ""),
        "pct_complete": int(f.get("pct_complete", 0) or 0),
        "next_action": f.get("next_action", ""),
        "completed_actions": f.get("completed_actions", ""),
        "blockers": f.get("blockers", ""),
        "last_updated_by": g.user["name"],
    }
    if g.user["role"] == "SLT":   # financial fields only for SLT
        for k in ("realized_revenue", "realized_ebitda", "realized_cost",
                  "forecasted_revenue", "forecasted_ebitda", "forecasted_cost"):
            if f.get(k) is not None:
                out[k] = parse_currency(f.get(k))
    return out


@app.route("/api/initiative/<item_id>", methods=["POST"])
def api_update(item_id):
    if g.user["role"] not in ("SLT", "PM"):
        abort(403)
    fields = _editable_from_form(request.form)
    ok = update_initiative(item_id, fields, sp_id=request.form.get("sp_id") or None)
    return _row_response(item_id, ok)


@app.route("/api/initiative", methods=["POST"])
@auth.require_role("SLT")
def api_create():
    fields = _editable_from_form(request.form)
    if not fields["name"]:
        return "Name is required", 400
    fields["category"] = request.form.get("category", "BOD")
    fields["sponsor"] = request.form.get("sponsor", g.user["name"])
    fields["owner"] = request.form.get("owner", g.user["name"])
    create_initiative(fields)
    return redirect(url_for("initiatives"))


@app.route("/api/initiative/<item_id>/delete", methods=["POST"])
@auth.require_role("SLT")
def api_delete(item_id):
    # Only a sponsor who owns the initiative may delete it.
    df = load_initiatives()
    row = df[df["id"].astype(str) == str(item_id)]
    sponsor = row.iloc[0]["sponsor"] if not row.empty else ""
    if not (settings.is_sponsor(g.user["name"]) and sponsor == g.user["name"]):
        abort(403)
    sp_id = row.iloc[0].get("sp_id") if not row.empty else None
    delete_initiative(item_id, sp_id=sp_id)
    return "", 200


@app.route("/api/subtask/<task_id>", methods=["POST"])
@auth.require_role("SLT", "PM", "TM")
def api_subtask_update(task_id):
    subs = load_sub_initiatives()
    idx = subs.index[subs["id"].astype(str) == str(task_id)]
    if len(idx):
        for k in ("status", "pct_complete", "next_action", "blockers"):
            if request.form.get(k) is not None:
                subs.loc[idx[0], k] = request.form.get(k)
        save_sub_initiatives(subs)
    return "", 200


def _row_response(item_id, ok):
    """After an inline save, re-render just that initiative row (HTMX swap)."""
    df = enrich_dataframe(load_initiatives())
    row = df[df["id"].astype(str) == str(item_id)]
    if row.empty:
        return "", 200
    return render_template("_row.html", r=row.iloc[0].to_dict(), saved=ok)


if __name__ == "__main__":
    # debug=True gives readable in-browser tracebacks; use_reloader=False keeps a
    # single process so run_service.py can track/stop it by PID reliably.
    app.run(host=settings.APP_HOST, port=settings.APP_PORT, debug=True, use_reloader=False)
