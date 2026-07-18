"""
data/notify.py
Task notifications: when SLT or a Leader is ready to release a task to its
assignee, or wants to request a status update, this composes and sends the email
(via mailer -> Microsoft Graph) AND records the nudge in-app so the assignee sees
it on their My Tasks even if email is off or they haven't opened their inbox.

Two stores on persistent storage:
  - notifications.json : {task_id: {kind, by, at, note}} - the latest pending
    nudge per task, shown to the assignee and cleared when they post an update.
  - user_emails.json   : {name_lower: email} - a name->email directory that fills
    as people sign in (auth.py) and can be hand-edited to fix any Graph can't
    resolve. Recipient resolution order: literal email -> this map -> Graph
    directory lookup -> unresolved (record the nudge, skip the email).
"""
import json
from pathlib import Path
from datetime import datetime

from config import settings

KINDS = {
    "release": {
        "label": "Task released",
        "subject": "A strategic task has been released to you: {task}",
        "lead": "{actor} has released this task to you and it's ready to start.",
    },
    "update": {
        "label": "Update requested",
        "subject": "Update requested on your strategic task: {task}",
        "lead": "{actor} has requested a status update on this task.",
    },
}


# ── small JSON store helpers ────────────────────────────────────────────────
def _read(path) -> dict:
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write(path, data: dict):
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── name -> email directory ─────────────────────────────────────────────────
def remember_email(name: str, email: str):
    """Learn a name->email pairing (called when a user signs in)."""
    if not name or not email or "@" not in email:
        return
    d = _read(settings.USER_EMAILS_PATH)
    key = name.strip().lower()
    if d.get(key) != email.strip():
        d[key] = email.strip()
        _write(settings.USER_EMAILS_PATH, d)


def _derive_email(name: str) -> str | None:
    """Guess firstname.lastname@domain from a display name (last resort). Uses the
    first and last whitespace tokens, so middle names/initials are dropped."""
    dom = settings.NOTIFY_EMAIL_DOMAIN
    parts = [p for p in (name or "").strip().split() if p]
    if not dom or len(parts) < 2:
        return None
    local = f"{parts[0]}.{parts[-1]}".lower()
    local = "".join(ch for ch in local if ch.isalnum() or ch == ".")
    return f"{local}@{dom}" if local.count(".") == 1 else None


def resolve_email(name: str):
    """Resolve an assignee's email. Returns (email|None, source) where source is
    literal | map | directory | derived - so the caller can flag a guessed
    address. Order: literal address -> learned/override map -> directory lookup
    -> derived from the name pattern."""
    n = (name or "").strip()
    if not n:
        return None, None
    if "@" in n:                                   # already an address
        return n, "literal"
    hit = _read(settings.USER_EMAILS_PATH).get(n.lower())
    if hit:
        return hit, "map"
    try:                                           # authoritative: the directory
        from data.graph_client import get_graph_client
        email = get_graph_client().find_user_email(n)
        if email:
            remember_email(n, email)               # cache it for next time
            return email, "directory"
    except Exception:
        pass
    derived = _derive_email(n)                      # last resort: the org pattern
    return (derived, "derived") if derived else (None, None)


# ── pending nudges (shown to the assignee) ──────────────────────────────────
def record(task_id, kind: str, by: str, note: str = ""):
    d = _read(settings.NOTIFY_PATH)
    d[str(task_id)] = {"kind": kind, "by": by, "note": note,
                       "at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    _write(settings.NOTIFY_PATH, d)


def pending(task_id) -> dict | None:
    return _read(settings.NOTIFY_PATH).get(str(task_id))


def clear(task_id):
    d = _read(settings.NOTIFY_PATH)
    if d.pop(str(task_id), None) is not None:
        _write(settings.NOTIFY_PATH, d)


# ── compose + send ──────────────────────────────────────────────────────────
def _html(kind: str, task: dict, actor: str, app_url: str, note: str) -> str:
    cfg = KINDS[kind]
    lead = cfg["lead"].format(actor=actor, task=task.get("name", "this task"))
    parent = task.get("parent_name") or ""
    rows = ""
    if parent:
        rows += f'<tr><td style="color:#64748b;padding:2px 12px 2px 0">Initiative</td><td><b>{parent}</b></td></tr>'
    if task.get("target_completion"):
        rows += f'<tr><td style="color:#64748b;padding:2px 12px 2px 0">Target</td><td>{task.get("target_completion")}</td></tr>'
    note_html = f'<p style="margin:10px 0;padding:10px;background:#f1f5f9;border-radius:6px">{note}</p>' if note else ""
    link = (f'<p style="margin:16px 0"><a href="{app_url}" '
            f'style="background:#5a8010;color:#fff;padding:9px 16px;border-radius:6px;'
            f'text-decoration:none;font-weight:700">Open My Tasks</a></p>') if app_url else ""
    return f"""<div style="font-family:Segoe UI,Arial,sans-serif;color:#0f172a;font-size:14px;max-width:560px">
      <h2 style="font-size:17px;margin:0 0 4px">{cfg['label']}</h2>
      <p style="margin:6px 0">{lead}</p>
      <h3 style="font-size:15px;margin:14px 0 4px">{task.get('name','(task)')}</h3>
      <table style="border-collapse:collapse;font-size:13px">{rows}</table>
      {note_html}{link}
      <p style="color:#94a3b8;font-size:12px;margin-top:18px">Sent from IEG Strategic Initiatives.</p>
    </div>"""


def notify_assignee(task: dict, kind: str, actor: str, app_url: str = "",
                    note: str = "") -> dict:
    """Record the nudge and email the task's assignee. Returns
    {recorded, emailed, to, message} - recording always happens; emailing depends
    on a resolvable address and MAIL_SENDER being configured."""
    if kind not in KINDS:
        return {"recorded": False, "emailed": False, "to": None, "message": "unknown notification type"}
    owner = str(task.get("owner") or "").strip()
    record(task.get("id"), kind, actor, note)

    to, source = resolve_email(owner)
    if not to:
        return {"recorded": True, "emailed": False, "to": None,
                "message": f"Recorded in-app. No email on file for {owner or 'the assignee'} "
                           f"- add it to user_emails.json to email them too."}

    import mailer
    cfg = KINDS[kind]
    res = mailer.send(to, cfg["subject"].format(task=task.get("name", "task")),
                      _html(kind, task, actor, app_url, note))
    guess = " (best-guess from name)" if source == "derived" else ""
    return {"recorded": True, "emailed": bool(res.get("ok")), "to": to,
            "message": (f"Emailed {to}{guess}." if res.get("ok")
                        else f"Recorded in-app; email not sent ({res.get('message')}).")}
