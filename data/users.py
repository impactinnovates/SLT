"""
data/users.py
Admin-editable user -> role store, layered over config/roles.yaml.

roles.yaml is the committed seed. The Admin screen writes overrides to a JSON
file on PERSISTENT storage (settings.USER_ROLES_PATH -> /home/site/data on Azure),
so role changes survive deploys and don't need a code push. An override wins over
the yaml seed for the same identity.

Role resolution order for a signed-in person:  override -> roles.yaml -> None.
The app treats "None" (unlisted) as the lowest role (Member) - see auth.py.
"""
import json
from pathlib import Path

from config import settings

VALID_ROLES = ("SLT", "Leader", "Member")


def _path() -> Path:
    return Path(settings.USER_ROLES_PATH)


def load_overrides() -> dict:
    try:
        p = _path()
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(d: dict):
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")


def set_role(identifier: str, role: str):
    """Add/update (or remove, if role is falsy) a user override. Keyed by the
    lower-cased identity (email/UPN or display name)."""
    key = str(identifier).strip().lower()
    if not key:
        return
    d = load_overrides()
    if role in VALID_ROLES:
        d[key] = role
    else:
        d.pop(key, None)
    _save(d)


def resolve_role(*identifiers):
    """First matching role across overrides then roles.yaml, else None."""
    ov = load_overrides()
    seed = {str(k).strip().lower(): v
            for k, v in (settings.ROLES_CONFIG.get("users") or {}).items()}
    for ident in identifiers:
        if not ident:
            continue
        k = str(ident).strip().lower()
        if k in ov:
            return ov[k]
        if k in seed:
            return seed[k]
    return None


def all_users() -> list:
    """Merged view for the Admin UI: [{identifier, role, source}] sorted by name."""
    merged = {}
    for name, role in (settings.ROLES_CONFIG.get("users") or {}).items():
        merged[str(name).strip().lower()] = {"identifier": name, "role": role, "source": "roles.yaml"}
    for ident, role in load_overrides().items():
        merged[str(ident).strip().lower()] = {"identifier": ident, "role": role, "source": "admin"}
    return sorted(merged.values(), key=lambda x: str(x["identifier"]).lower())
