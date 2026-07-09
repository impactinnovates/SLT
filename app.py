"""
app.py - IEG Strategic Initiatives (Flask + Jinja2 + HTMX).

Model:
  Initiative (SLT-owned, BOD-reported, financials)  -- one List, task_type field
    └── Task (assigned to a Leader; parent_id -> initiative)  -- rolls up to parent

Roles (config/roles.yaml, matched to the signed-in Microsoft identity):
  SLT     - all initiatives + tasks + financials + board report; create/assign; delete (if sponsor)
  Leader  - ONLY tasks they own or assigned to their team; never sees initiatives/financials
  Member  - ONLY tasks assigned to them; status/progress updates

Visibility is enforced server-side: Leader/Member requests can never load initiatives.

Run (dev):  python app.py            -> http://127.0.0.1:8502   (?as=SLT|Leader|Member to preview)
Run (prod): gunicorn -b 0.0.0.0:8502 wsgi:app
"""
from datetime import timedelta, date, datetime

import pandas as pd
from flask import (Flask, render_template, request, redirect, url_for,
                   session, g, abort)

from config import settings
import auth
from data.loader import (load_initiatives, update_initiative, create_initiative,
                         delete_initiative, create_task, clear_cache)
from data import source
from data.models import STATUS_COLORS, STATUS_ICONS, TYPE_TASK
from utils.pacing import enrich_dataframe, summary_stats
from utils import rollup
from components import financial_charts as fc

app = Flask(__name__)
app.secret_key = settings.SESSION_SECRET or "dev-only-insecure-key-change-me"
app.permanent_session_lifetime = timedelta(hours=8)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=bool(settings.ENTRA_CLIENT_ID))

app.register_blueprint(auth.bp)
app.before_request(auth.require_login)

# Nightly Cost Takeout Tracker -> List sync (no-op unless SYNC_SCHEDULE_ENABLED).
from data import scheduler  # noqa: E402
scheduler.start()

STATUSES = ["On Track", "At Risk", "Behind", "Blocked", "Not Started", "Completed"]
TASK_STATUSES = ["Not Started", "On Track", "At Risk", "Behind", "Blocked", "Completed"]
SEV = {"Behind": 0, "Blocked": 1, "At Risk": 2, "Not Started": 3, "On Track": 4, "Completed": 5}


# ── Jinja helpers ───────────────────────────────────────────────────────────
@app.template_filter("currency")
def _currency(val):
    if val is None or (isinstance(val, float) and val != val):
        return "-"
    try:
        return f"${float(val):,.0f}"
    except (TypeError, ValueError):
        return "-"


@app.template_filter("date")
def _date(val):
    if val is None or (isinstance(val, float) and val != val) or val == "":
        return "-"
    if isinstance(val, (date, datetime)):
        return val.strftime("%b %d, %Y")
    return str(val)


@app.template_filter("date_iso")
def _date_iso(val):
    """YYYY-MM-DD for prefilling <input type=date>; empty when unknown."""
    if isinstance(val, (date, datetime)):
        return val.strftime("%Y-%m-%d")
    s = str(val or "").strip()
    return s[:10] if len(s) >= 10 and s[4] == "-" else ""


@app.template_global()
def url_with(**changes):
    """Current query string with some keys overridden (None removes a key). Used
    for filter-preserving links (KPI cards, metric/dimension toggles)."""
    from urllib.parse import urlencode
    args = request.args.to_dict(flat=False)
    for k, v in changes.items():
        if v is None:
            args.pop(k, None)
        else:
            args[k] = [v]
    flat = [(k, vv) for k, vs in args.items() for vv in vs]
    return ("?" + urlencode(flat)) if flat else ""


@app.template_global()
def alert_reason(row):
    return rollup.alert_reason(row)


@app.context_processor
def _inject():
    return {"user": getattr(g, "user", None),
            "source_label": source.source_label(),
            "status_colors": STATUS_COLORS, "status_icons": STATUS_ICONS,
            "auth_enabled": auth.AUTH_ENABLED, "is_admin": auth.is_admin(),
            "statuses": STATUSES, "task_statuses": TASK_STATUSES,
            "leaders": sorted(settings.ROLES_CONFIG.get("users", {}).keys())}


# ── Data helpers ────────────────────────────────────────────────────────────
def _hierarchy():
    """(initiatives_enriched_with_rollup, tasks_with_rollup). Single source for
    every view. Roll-up runs on ALL rows first so it nests sub-task -> task ->
    initiative; then we split and add pacing to the initiatives."""
    raw = load_initiatives()
    raw = rollup.attach_rollup(raw)
    inits, tasks = rollup.split_hierarchy(raw)
    inits = enrich_dataframe(inits)
    return inits, tasks


def _identity(user) -> set:
    return {str(user.get("name", "")).strip().lower(),
            str(user.get("email", "")).strip().lower()}


def _my_tasks(tasks: pd.DataFrame, user) -> pd.DataFrame:
    """Role-scoped tasks. SLT: all. Leader: owned or assigned-by-me. Member: owned."""
    if tasks.empty:
        return tasks
    role = user["role"]
    if role == "SLT":
        return tasks
    me = _identity(user)
    owner = tasks.get("owner", pd.Series([""] * len(tasks))).astype(str).str.strip().str.lower()
    if role == "Member":
        return tasks[owner.isin(me)]
    creator = tasks.get("created_by", pd.Series([""] * len(tasks))).astype(str).str.strip().str.lower()
    return tasks[owner.isin(me) | creator.isin(me)]


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    a = request.args
    spon, own = a.getlist("sponsor"), a.getlist("owner")
    mask = pd.Series([True] * len(df), index=df.index)
    if spon or own:
        sm = df["sponsor"].isin(spon) if spon and "sponsor" in df else pd.Series([False] * len(df), index=df.index)
        om = df["owner"].isin(own) if own and "owner" in df else pd.Series([False] * len(df), index=df.index)
        mask &= (sm | om)
    for col in ("status", "region"):
        vals = a.getlist(col)
        if vals and col in df.columns:
            mask &= df[col].isin(vals)
    if a.get("show_completed", "1") not in ("1", "true", "on") and "status" in df.columns:
        mask &= df["status"] != "Completed"
    q = (a.get("q") or "").strip()
    if q and "name" in df.columns:
        mask &= df["name"].astype(str).str.contains(q, case=False, na=False, regex=False)
    return df[mask].copy()


def _options(df):
    def uniq(c):
        return sorted(df[c].dropna().unique().tolist()) if c in df.columns else []
    return {"sponsors": uniq("sponsor"), "owners": uniq("owner"),
            "statuses": uniq("status"), "regions": uniq("region")}


def _sort(df, how):
    if df.empty:
        return df
    if how == "pri_sev":
        df = df.copy()
        df["_sev"] = df["status"].map(SEV).fillna(9)
        df["_pri"] = pd.to_numeric(df.get("priority"), errors="coerce").fillna(9)
        return df.sort_values(["_pri", "_sev", "name"])
    if how in df.columns:
        return df.sort_values(how, ascending=(how != "pct_complete"), na_position="last")
    return df


def _tasks_by_parent(tasks: pd.DataFrame) -> dict:
    out = {}
    if tasks.empty:
        return out
    for pid, grp in tasks.groupby(tasks["parent_id"].astype(str)):
        out[str(pid)] = grp.to_dict("records")
    return out


def _fig(fig):
    return fig.to_json()


def _require(perm):
    if not settings.get_permissions(g.user["role"]).get(perm):
        abort(403)


# ── Landing ─────────────────────────────────────────────────────────────────
@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/")
def home():
    return redirect("/dashboard" if g.user["role"] == "SLT" else "/tasks")


@app.route("/refresh")
def refresh():
    """Force an immediate re-read from the List (bypass the cache TTL)."""
    clear_cache()
    return redirect(request.referrer or "/")


# ── SLT: dashboard (now also carries the Performance gauges + breakdown) ─────
@app.route("/dashboard")
@auth.require_role("SLT")
def dashboard():
    from utils import performance as perf
    inits, tasks = _hierarchy()
    inits = _apply_filters(inits)
    stats = summary_stats(inits)
    yf = perf.year_fraction()
    fin = inits[inits["forecasted_ebitda"].notna() | inits["realized_ebitda"].notna()].copy() \
        if "forecasted_ebitda" in inits.columns else inits.iloc[0:0]
    ebitda = perf.summarize(fin, yf)
    progress = perf.progress_summary(inits, yf)
    by = request.args.get("by", "region")
    dim = by if by in ("region", "sponsor", "owner") else "region"
    metric = request.args.get("metric", "ebitda")
    metric = metric if metric in ("ebitda", "progress") else "ebitda"
    groups = (perf.progress_by_dimension(inits, dim, yf) if metric == "progress"
              else perf.by_dimension(fin, dim, yf))
    # Each breakdown card drills to the Initiatives list filtered by the current
    # dashboard filters PLUS this group's dimension value (e.g. region=Clare, MI).
    from urllib.parse import urlencode
    keep = {k: request.args.getlist(k) for k in request.args if k not in ("by", "metric", "alerts")}
    for grp in groups:
        lbl = grp.get("label")
        if lbl and lbl != "(unassigned)":
            a = {**keep, dim: [lbl]}
            grp["drill"] = "/initiatives?" + urlencode([(k, vv) for k, vs in a.items() for vv in vs])
        else:
            grp["drill"] = None
    n_alerts = int(inits.apply(rollup.needs_attention, axis=1).sum()) if not inits.empty else 0
    return render_template("dashboard.html", nav="dashboard", stats=stats, ebitda=ebitda,
                           progress=progress, groups=groups, by=dim, metric=metric,
                           n_alerts=n_alerts, options=_options(inits), args=request.args,
                           task_total=len(tasks))


# ── SLT: initiatives with task breakdown ────────────────────────────────────
@app.route("/initiatives")
@auth.require_role("SLT")
def initiatives():
    inits, tasks = _hierarchy()
    total = len(inits)
    shown = _apply_filters(inits)
    if request.args.get("alerts") == "1" and not shown.empty:
        shown = shown[shown.apply(rollup.needs_attention, axis=1)]
    how = request.args.get("sort", "pri_sev")
    rows = _sort(shown, how).to_dict("records")
    leaders = sorted(settings.ROLES_CONFIG.get("users", {}).keys())
    return render_template("initiatives.html", nav="initiatives", rows=rows,
                           tasks_by_parent=_tasks_by_parent(tasks), shown=len(shown),
                           total=total, sort=how, options=_options(inits),
                           args=request.args, leaders=leaders,
                           statuses=STATUSES, task_statuses=TASK_STATUSES)


@app.route("/financial")
@auth.require_role("SLT")
def financial():
    inits, _ = _hierarchy()
    inits = _apply_filters(inits)
    stats = summary_stats(inits)
    has_fin = "forecasted_ebitda" in inits.columns
    er = inits[inits["forecasted_ebitda"].notna()].copy() if has_fin else inits.iloc[0:0]
    pace = {"on": int((er["ebitda_pace_score"] >= 1.0).sum()) if not er.empty else 0,
            "at": int(((er["ebitda_pace_score"] >= 0.75) & (er["ebitda_pace_score"] < 1.0)).sum()) if not er.empty else 0,
            "behind": int((er["ebitda_pace_score"] < 0.75).sum()) if not er.empty else 0,
            "nodata": int(er["ebitda_pace_score"].isna().sum()) if not er.empty else 0}
    # Per-initiative financial rows: anything with a forecast OR a realized figure,
    # biggest budget first. This CSS list is the mobile-readable core of the page.
    if has_fin:
        fin = inits[inits["forecasted_ebitda"].notna() | inits["realized_ebitda"].notna()].copy()
        fin["_sortk"] = fin["forecasted_ebitda"].fillna(fin["realized_ebitda"]).fillna(0)
        fin = fin.sort_values("_sortk", ascending=False)
    else:
        fin = inits.iloc[0:0]
    return render_template("financial.html", nav="financial", stats=stats, pace=pace,
                           curve=_fig(fc.ebitda_cumulative_curve(inits)),
                           fin_rows=fin.to_dict("records"),
                           options=_options(inits), args=request.args)


@app.route("/performance")
@auth.require_role("SLT")
def performance():
    # Folded into the Dashboard; keep the URL working (preserve any query).
    return redirect("/dashboard" + (("?" + request.query_string.decode()) if request.query_string else ""))


@app.route("/timeline")
@auth.require_role("SLT")
def timeline():
    inits, _ = _hierarchy()
    inits = _apply_filters(inits)
    return render_template("timeline.html", nav="timeline",
                           chart=_fig(fc.completion_timeline(inits)),
                           options=_options(inits), args=request.args)


@app.route("/new")
@auth.require_role("SLT")
def new_initiative():
    src = "live" if settings.graph_is_configured() else "csv"
    return render_template("new.html", nav="new", statuses=STATUSES,
                           source_label=src, writes=settings.LIST_WRITE_ENABLED)


# ── SLT: board report (print/PDF-friendly) ──────────────────────────────────
@app.route("/board")
@auth.require_role("SLT")
def board():
    inits, tasks = _hierarchy()
    inits = _apply_filters(inits)
    inits = _sort(inits, "pri_sev")
    stats = summary_stats(inits)
    att = inits[inits.apply(rollup.needs_attention, axis=1)]
    return render_template("board.html", nav="board", stats=stats,
                           rows=inits.to_dict("records"),
                           attention=att.to_dict("records"),
                           tasks_by_parent=_tasks_by_parent(tasks),
                           generated=date.today().strftime("%B %d, %Y"))


# ── SLT: Excel -> List savings sync ─────────────────────────────────────────
@app.route("/sync")
@auth.require_role("SLT")
def sync_page():
    from data import excel_sync
    try:
        updates, _ = excel_sync.compute_updates()
        err = None
    except Exception as e:
        updates, err = [], str(e)[:300]
    return render_template("sync.html", nav="sync", updates=updates, err=err,
                           writes_on=settings.LIST_WRITE_ENABLED)


@app.route("/api/sync/cost-takeout", methods=["POST"])
@auth.require_role("SLT")
def api_sync():
    from data import excel_sync
    only = request.form.get("only") or None
    updates, cfg = excel_sync.compute_updates()
    results = excel_sync.apply_updates(updates, cfg, only=only)
    return render_template("sync_result.html", results=results)


# ── Admin: user access management (admins only, per ADMIN_EMAILS) ────────────
@app.route("/admin")
@auth.require_admin
def admin():
    from data import users
    return render_template("admin.html", nav="admin", users=users.all_users(),
                           roles=users.SETTABLE, admins=sorted(settings.ADMIN_EMAILS))


@app.route("/api/admin/user", methods=["POST"])
@auth.require_admin
def api_admin_user():
    from data import users
    ident = (request.form.get("identifier") or "").strip()
    action = request.form.get("action", "")
    role = (request.form.get("role") or "").strip()
    if not ident:
        return "identifier required", 400
    if action == "delete":
        users.delete_user(ident)
    else:
        if role and role not in users.SETTABLE:
            return "invalid role", 400
        users.set_role(ident, role)      # blank role removes the override
    return redirect("/admin")


# ── Leader / Member: task workspace ─────────────────────────────────────────
@app.route("/tasks")
def tasks_view():
    if g.user["role"] == "SLT":
        return redirect("/initiatives")
    inits, tasks = _hierarchy()
    mine = _my_tasks(tasks, g.user)
    # Parent initiative NAME only (never its strategic/financial detail).
    pname = {str(r["id"]): r.get("name", "") for _, r in inits.iterrows()} if not inits.empty else {}
    subs_by_parent = _tasks_by_parent(tasks)   # task id -> its sub-tasks
    mine_records = mine.to_dict("records")
    for t in mine_records:
        t["parent_name"] = pname.get(str(t.get("parent_id", "")), "")
        t["subs"] = subs_by_parent.get(str(t.get("id", "")), [])
    can_assign = settings.get_permissions(g.user["role"]).get("assign_task")
    return render_template("tasks.html", nav="tasks", tasks=mine_records,
                           task_statuses=TASK_STATUSES, can_assign=can_assign)


# ── Write endpoints ─────────────────────────────────────────────────────────
def _editable(f) -> dict:
    from data.models import parse_currency
    out = {"name": f.get("name", "").strip(), "status": f.get("status", ""),
           "pct_complete": int(f.get("pct_complete", 0) or 0),
           "next_action": f.get("next_action", ""), "blockers": f.get("blockers", ""),
           "completed_actions": f.get("completed_actions", ""),
           "last_updated_by": g.user["name"]}
    if g.user["role"] == "SLT":
        for k in ("realized_revenue", "realized_ebitda", "realized_cost",
                  "forecasted_revenue", "forecasted_ebitda", "forecasted_cost"):
            if f.get(k) is not None:
                out[k] = parse_currency(f.get(k))
        # Dates: capture the raw input; loader._to_graph_fields formats for the List.
        for k in ("start_date", "target_completion", "revised_completion",
                  "actual_completion", "benefit_start_date"):
            v = (f.get(k) or "").strip()
            if v:
                out[k] = v
        # Key metadata: only overwrite fields actually submitted by the form.
        for k in ("owner", "sponsor", "region", "priority", "description"):
            if f.get(k) is not None:
                out[k] = f.get(k).strip() if isinstance(f.get(k), str) else f.get(k)
    return out


@app.route("/api/initiative/<item_id>", methods=["POST"])
@auth.require_role("SLT")
def api_update(item_id):
    update_initiative(item_id, _editable(request.form), sp_id=request.form.get("sp_id") or None)
    return _row(item_id)


@app.route("/api/initiative", methods=["POST"])
@auth.require_role("SLT")
def api_create():
    fields = _editable(request.form)
    if not fields["name"]:
        return "Name is required", 400
    fields.update(task_type="Initiative", category=request.form.get("category", ""),
                  region=request.form.get("region", ""),
                  sponsor=request.form.get("sponsor", g.user["name"]),
                  owner=request.form.get("owner", g.user["name"]))
    create_initiative(fields)
    return redirect(url_for("initiatives"))


@app.route("/api/initiative/<item_id>/delete", methods=["POST"])
@auth.require_role("SLT")
def api_delete(item_id):
    inits, _ = rollup.split_hierarchy(load_initiatives())
    row = inits[inits["id"].astype(str) == str(item_id)]
    sponsor = row.iloc[0]["sponsor"] if not row.empty else ""
    if not (settings.is_sponsor(g.user["name"]) and sponsor == g.user["name"]):
        abort(403)
    delete_initiative(item_id, sp_id=(row.iloc[0].get("sp_id") if not row.empty else None))
    return "", 200


@app.route("/api/initiative/<parent_id>/task", methods=["POST"])
def api_create_task(parent_id):
    """SLT adds a task under any initiative; a Leader adds a sub-task ONLY under a
    task they own or created. Members cannot create tasks (create_task=false)."""
    _require("create_task")
    if g.user["role"] != "SLT":
        # A Leader may only nest under one of their own tasks - never an initiative
        # (initiatives aren't in the tasks frame, so this also blocks that path).
        _, _tasks = rollup.split_hierarchy(load_initiatives())
        prow = _tasks[_tasks["id"].astype(str) == str(parent_id)]
        me = _identity(g.user)
        owns = (not prow.empty and
                (str(prow.iloc[0].get("owner", "")).lower() in me
                 or str(prow.iloc[0].get("created_by", "")).lower() in me))
        if not owns:
            abort(403)
    owner = request.form.get("owner", "").strip() or g.user["name"]
    name = request.form.get("name", "").strip()
    if not name:
        return "Task name required", 400
    create_task(parent_id, {
        "name": name, "status": request.form.get("status", "Not Started"),
        "pct_complete": int(request.form.get("pct_complete", 0) or 0),
        "next_action": request.form.get("next_action", ""),
        "target_completion": request.form.get("target_completion", ""),
        "last_updated_by": g.user["name"],
    }, owner=owner, creator=g.user["name"])
    if g.user["role"] == "SLT":
        return _row(parent_id)                      # refresh the initiative row
    return redirect("/tasks")


@app.route("/api/task/<task_id>", methods=["POST"])
def api_task_update(task_id):
    """Update a task. SLT: any. Leader: their team's. Member: their own."""
    _, tasks = rollup.split_hierarchy(load_initiatives())
    row = tasks[tasks["id"].astype(str) == str(task_id)]
    if row.empty:
        abort(404)
    t = row.iloc[0]
    me = _identity(g.user)
    role = g.user["role"]
    allowed = (role == "SLT"
               or (role == "Leader" and (str(t.get("owner", "")).lower() in me or str(t.get("created_by", "")).lower() in me))
               or (role == "Member" and str(t.get("owner", "")).lower() in me))
    if not allowed:
        abort(403)
    fields = {"status": request.form.get("status", t.get("status")),
              "pct_complete": int(request.form.get("pct_complete", 0) or 0),
              "next_action": request.form.get("next_action", ""),
              "blockers": request.form.get("blockers", ""),
              "last_updated_by": g.user["name"]}
    update_initiative(task_id, fields, sp_id=(t.get("sp_id") or None))
    return "", 200


def _row(item_id):
    """Re-render one initiative row (HTMX swap) with fresh roll-up."""
    inits, tasks = _hierarchy()
    row = inits[inits["id"].astype(str) == str(item_id)]
    if row.empty:
        return "", 200
    return render_template("_row.html", r=row.iloc[0].to_dict(),
                           children=rollup.children_of(tasks, item_id).to_dict("records"),
                           leaders=sorted(settings.ROLES_CONFIG.get("users", {}).keys()),
                           statuses=STATUSES, task_statuses=TASK_STATUSES)


if __name__ == "__main__":
    app.run(host=settings.APP_HOST, port=settings.APP_PORT, debug=True, use_reloader=False)
