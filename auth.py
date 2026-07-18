"""
auth.py - Microsoft Entra ID single sign-on for the SLT dashboard.

Same Entra auth-code pattern as DemandPulse / SCP, trimmed to what this app
needs: identity only. There is NO user table here - a person's access layer
(SLT / PM / TM) is looked up live from config/roles.yaml against their signed-in
identity, so access changes are a one-line yaml edit with no DB migration.

Flow:
  any page      -> not signed in -> redirect to /auth/login
  /auth/login   -> build Entra auth-code URL with a state nonce; redirect
  /auth/callback-> exchange code for tokens (msal validates signature/expiry);
                   confirm tenant id; resolve role from roles.yaml; store the
                   user in the (regenerated) session
  /auth/logout  -> destroy session, redirect through Entra logout

SSO enforces ONLY when ENTRA_CLIENT_ID is configured. Locally (no Entra vars)
the app runs open as a dev SLT user so the whole thing is viewable without a
tenant - exactly like DemandPulse's local mode.

Required env when SSO is on (see .env.template):
  ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_TENANT_ID, ENTRA_REDIRECT_URI,
  SESSION_SECRET. Optional: POST_LOGOUT_REDIRECT_URI.
"""
import os
import secrets
from functools import wraps
from urllib.parse import urlencode

from flask import (Blueprint, current_app, request, session, redirect,
                   url_for, abort, g)
import msal

from config import settings

bp = Blueprint("auth", __name__)

AUTH_ENABLED = bool(settings.ENTRA_CLIENT_ID)

# Identity used for local, no-SSO development so every layer is viewable.
DEV_USER = {
    "name":  "Chad Abrahamson (dev)",
    "email": "chadlabrahamson@iegna.com",
    "role":  "SLT",
    "oid":   "local-dev",
}

# Dev-only role preview: in local (no-SSO) mode, ?as=SLT|Leader|Member switches
# the dev user's generic role, and ?who=<name> steps into a specific real person
# (their resolved role + their identity, so task filtering scopes to THEIR work -
# the accurate "what does this user actually see" check). Ignored when SSO is on.
_DEV_ROLES = {"SLT", "Leader", "Member"}


def _dev_user():
    from flask import request, session
    from data import users
    # ?who and ?as are mutually exclusive preview modes; setting one clears the other.
    if "who" in request.args:
        who = request.args.get("who", "").strip()
        session.pop("dev_role", None)
        if who:
            session["dev_who"] = who
        else:
            session.pop("dev_who", None)          # who= (empty) resets to self
    elif request.args.get("as") in _DEV_ROLES:
        session["dev_role"] = request.args["as"]
        session.pop("dev_who", None)

    who = session.get("dev_who")
    if who:
        # Their real role (unlisted -> Member, exactly as the live app treats them),
        # and name+email set to `who` so _identity() matches their assigned tasks.
        role = users.resolve_role(who) or "Member"
        return {**DEV_USER, "name": who, "email": who, "role": role,
                "oid": "preview:" + who}
    role = session.get("dev_role", DEV_USER["role"])
    name = DEV_USER["name"] if role == "SLT" else f"Dev {role}"
    return {**DEV_USER, "role": role, "name": name}


def msal_app():
    return msal.ConfidentialClientApplication(
        client_id=settings.ENTRA_CLIENT_ID,
        client_credential=settings.ENTRA_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}",
    )


# ── Session identity helpers ────────────────────────────────────────────────
def current_user() -> dict | None:
    """The signed-in user dict {name, email, role, oid}, or None."""
    if not AUTH_ENABLED:
        return _dev_user()
    return session.get("user")


def load_user():
    """before_request hook target: stash the user (or None) on g."""
    g.user = current_user()


def require_login():
    """App-wide gate. Public: /auth/* and /healthz. Everything else needs a
    signed-in session; API calls get 401 instead of a redirect."""
    if not AUTH_ENABLED:
        g.user = _dev_user()
        return
    if request.path.startswith("/auth/") or request.path == "/healthz":
        return
    user = session.get("user")
    if not user:
        if request.path.startswith("/api/"):
            abort(401)
        session["next_url"] = request.path
        return redirect(url_for("auth.login"))
    # Re-resolve the role live each request so an admin's role change or a
    # disable takes effect immediately, not just at next sign-in.
    from data import users
    role = users.resolve_role(user.get("email"), user.get("name")) or "Member"
    if role == users.DISABLED:
        session.clear()
        abort(403, "Your access to this app has been disabled.")
    user = {**user, "role": role}
    session["user"] = user
    g.user = user


def require_role(*roles):
    """Route decorator: allow only the given SLT / Leader / Member roles."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            user = current_user()
            if not user or user["role"] not in roles:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def is_admin(user=None) -> bool:
    """May the user open the Admin screen? Authoritative source is the
    ADMIN_EMAILS env var (set only on the Azure app), so admin rights can't be
    granted from inside the app. Local dev (no SSO) is admin for testing."""
    user = user or current_user()
    if not user:
        return False
    if not AUTH_ENABLED:
        return True
    email = str(user.get("email", "")).strip().lower()
    return bool(settings.ADMIN_EMAILS) and email in settings.ADMIN_EMAILS


def require_admin(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not is_admin():
            abort(403)
        return fn(*a, **kw)
    return wrapper


# ── Routes ──────────────────────────────────────────────────────────────────
@bp.route("/auth/login")
def login():
    session["auth_state"] = secrets.token_urlsafe(24)
    url = msal_app().get_authorization_request_url(
        scopes=[],
        state=session["auth_state"],
        redirect_uri=settings.ENTRA_REDIRECT_URI,
    )
    return redirect(url)


@bp.route("/auth/callback")
def callback():
    if request.args.get("state") != session.get("auth_state"):
        abort(403, "Invalid state")
    session.pop("auth_state", None)

    code = request.args.get("code")
    if not code:
        abort(400, request.args.get("error_description") or "Missing code")

    result = msal_app().acquire_token_by_authorization_code(
        code=code, scopes=[], redirect_uri=settings.ENTRA_REDIRECT_URI,
    )
    if "error" in result:
        current_app.logger.warning("Auth callback error: %s", result.get("error"))
        abort(400, "Sign-in failed")

    claims = result.get("id_token_claims", {}) or {}
    if claims.get("tid") != settings.ENTRA_TENANT_ID:
        abort(403, "Wrong tenant")

    name  = claims.get("name")
    email = claims.get("preferred_username") or claims.get("upn") or ""
    oid   = claims.get("oid")
    if not oid:
        abort(400, "Token missing oid")

    # Access layer: admin-managed overrides first, then roles.yaml, else Member.
    from data import users
    role = users.resolve_role(name, email) or "Member"

    # Learn this person's name->email so task notifications can reach them even if
    # the directory lookup is unavailable.
    try:
        from data import notify
        notify.remember_email(name, email)
    except Exception:
        pass

    next_url = session.pop("next_url", "/")
    session.clear()                       # defeat session fixation (no regenerate in Flask)
    session["user"] = {"name": name, "email": email, "role": role, "oid": oid}
    session.permanent = True
    return redirect(next_url)


@bp.route("/auth/logout")
def logout():
    session.clear()
    if not AUTH_ENABLED:
        return redirect("/")
    qs = urlencode({"post_logout_redirect_uri":
                    os.environ.get("POST_LOGOUT_REDIRECT_URI", request.host_url)})
    return redirect(
        f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}"
        f"/oauth2/v2.0/logout?{qs}")
