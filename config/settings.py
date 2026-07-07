"""
config/settings.py
Central configuration for the IEG Strategic Initiatives platform.

Loads environment (.env locally, App Service settings on Azure) and roles.yaml.
Two auth surfaces are kept deliberately separate:

  1. Microsoft Entra SSO   -> WHO is signing in            (ENTRA_*)   -> auth.py
  2. App-only Graph client -> HOW the app reads/writes the -> graph_client.py
     List as a service identity                            (GRAPH_* / SHAREPOINT_*)

The List connection is considered "live" only when graph_is_configured() is True
(tenant + client id + secret + site URL all present). Until then the app falls
back to the local CSV export so it stays fully usable — no code change to go live.
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# ── App ─────────────────────────────────────────────────────────
APP_PORT = int(os.getenv("APP_PORT", 8502))
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")   # localhost by default; Azure binds via gunicorn

# ── Data locations ──────────────────────────────────────────────
# The base CSV export is committed seed data (read-only). The edit overlays are
# runtime state and MUST live on persistent storage: on Azure App Service only
# /home/site/data survives restarts AND redeploys (the code folder is replaced
# on every deploy). Locally they sit in the repo's data/ folder.
def _data_dir() -> Path:
    if os.environ.get("WEBSITE_SITE_NAME"):          # set by Azure App Service
        d = Path("/home/site/data")
        d.mkdir(parents=True, exist_ok=True)
        return d
    return ROOT / "data"


DATA_DIR = _data_dir()


def _resolve(env_key: str, default: Path) -> Path:
    """Env override wins; a relative override resolves against the repo root."""
    v = os.getenv(env_key)
    if not v:
        return default
    p = Path(v)
    return p if p.is_absolute() else ROOT / p


CSV_PATH             = _resolve("CSV_PATH",             ROOT / "data" / "Strategic_Initiatives_2026.csv")
EDITS_PATH           = _resolve("EDITS_PATH",           DATA_DIR / "edits.json")
SUB_INITIATIVES_PATH = _resolve("SUB_INITIATIVES_PATH", DATA_DIR / "sub_initiatives.json")

# ── Microsoft Entra SSO (user sign-in) ──────────────────────────
ENTRA_CLIENT_ID     = os.getenv("ENTRA_CLIENT_ID", "")
ENTRA_CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET", "")
ENTRA_TENANT_ID     = os.getenv("ENTRA_TENANT_ID", "")
ENTRA_REDIRECT_URI  = os.getenv("ENTRA_REDIRECT_URI", "")
SESSION_SECRET      = os.getenv("SESSION_SECRET", "")

# ── App-only Microsoft Graph (List read/write as a service identity) ──
# The SharePoint site that hosts the Strategic Initiatives List (confirmed by Chad).
SHAREPOINT_SITE_URL = os.getenv(
    "SHAREPOINT_SITE_URL",
    "https://iegna.sharepoint.com/sites/2023IEGStrategicPlan",
)
# Exact display name of the List. Leave blank to discover it via the probe.
LIST_NAME = os.getenv("LIST_NAME", "")

# Graph app credentials. If a dedicated GRAPH_* app isn't supplied, fall back to
# the ENTRA_* app so a single registration can serve both sign-in and List access.
GRAPH_TENANT_ID     = os.getenv("GRAPH_TENANT_ID",     ENTRA_TENANT_ID)
GRAPH_CLIENT_ID     = os.getenv("GRAPH_CLIENT_ID",     ENTRA_CLIENT_ID)
GRAPH_CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET", "")

# Writes to the List are OFF by default even when reads are live: we only turn
# them on after the probe confirms the real internal column names and GRAPH_MAP
# is reconciled. Until then edits are staged safely in the local overlay.
LIST_WRITE_ENABLED = os.getenv("LIST_WRITE_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def graph_is_configured() -> bool:
    """True when the app has everything it needs to talk to the List as a service
    identity. Until then the app serves the local CSV export."""
    return all([GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, SHAREPOINT_SITE_URL])


# Backward-compatible aliases (graph_client.py historically imported these names).
TENANT_ID     = GRAPH_TENANT_ID
CLIENT_ID     = GRAPH_CLIENT_ID
CLIENT_SECRET = GRAPH_CLIENT_SECRET

# ── Roles (SLT / PM / TM) ───────────────────────────────────────
_roles_path = ROOT / "config" / "roles.yaml"


def load_roles() -> dict:
    with open(_roles_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


ROLES_CONFIG = load_roles()


def _users_lower() -> dict:
    """roles.yaml keys, lower-cased, for case-insensitive identity matching."""
    return {str(k).lower(): v for k, v in (ROLES_CONFIG.get("users") or {}).items()}


def get_user_role(*identifiers) -> str:
    """Return SLT / PM / TM for the first identifier that matches roles.yaml
    (case-insensitive). Pass any of: display name, email, UPN. Entra sign-in gives
    us all three, so we try each. Defaults to 'TM' for a signed-in but unlisted user.

    roles.yaml currently keys on display names; once we confirm the sign-in claims
    we can re-key to emails for a more reliable match (recommended)."""
    lut = _users_lower()
    for ident in identifiers:
        if ident and str(ident).lower() in lut:
            return lut[str(ident).lower()]
    return "TM"


def is_known_user(*identifiers) -> bool:
    lut = _users_lower()
    return any(ident and str(ident).lower() in lut for ident in identifiers)


def get_permissions(role: str) -> dict:
    return (ROLES_CONFIG.get("permissions") or {}).get(role, {})


def is_sponsor(username: str) -> bool:
    sponsors = [str(s).lower() for s in (ROLES_CONFIG.get("sponsors") or [])]
    return str(username).lower() in sponsors


def all_users() -> list:
    return sorted((ROLES_CONFIG.get("users") or {}).keys())
