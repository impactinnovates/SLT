"""
data/loader.py
Loads initiatives (via data/source.py: live List or local CSV), cleans/types the
frame, and applies the local edit overlay. Also handles writes.

Write policy (deliberate and safe):
  - Reads can be live from the SharePoint List as soon as GRAPH_* is configured.
  - Writes go to the live List ONLY when settings.LIST_WRITE_ENABLED is true AND
    the item has a SharePoint id. Until then (the default), every edit is staged
    in data/edits.json so nothing is lost and nothing is written to the List
    before the field mapping is confirmed by the probe.

This module is framework-free (no Streamlit); the Flask app imports it directly.
"""
import re
import json
import time
import uuid
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Last write error, so a failed save can be shown to the user instead of vanishing.
_LAST_ERROR = {"msg": None}


def _set_error(msg):
    _LAST_ERROR["msg"] = msg


def last_error():
    return _LAST_ERROR["msg"]

from config import settings
from data import source
from data.models import (CSV_MAP, INTERNAL_TO_GRAPH, TYPE_TASK, TYPE_INITIATIVE,
                         parse_currency, parse_pct, parse_date)

# In-process cache with a short TTL so a burst of requests doesn't hammer Graph,
# but List changes (incl. writes from the sync CLI in another process) still show
# up within a couple of minutes. clear_cache() (or ?refresh) forces an immediate
# re-read.
_CACHE: dict = {}
_CACHE_TTL = 120  # seconds


def clear_cache():
    _CACHE.clear()


# ── Edit overlay (field-level, keyed by initiative id) ──────────────────────
def _load_edits() -> dict:
    try:
        p = Path(settings.EDITS_PATH)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_edits(edits: dict):
    p = Path(settings.EDITS_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(edits, indent=2, default=str), encoding="utf-8")


# ── Load + clean ────────────────────────────────────────────────────────────
def load_initiatives(force: bool = False) -> pd.DataFrame:
    fresh = (time.time() - _CACHE.get("_ts", 0)) < _CACHE_TTL
    if not force and fresh and "initiatives" in _CACHE:
        return _CACHE["initiatives"].copy()
    df = source.fetch_initiatives()
    df = _clean_df(df)
    # The overlay is a STAGING fallback for when we can't write to the List. Once
    # live write-back is on, applying it can only mask what the List really says
    # (a stale staged value would silently shadow a real save), so skip it.
    if not (settings.LIST_WRITE_ENABLED and settings.graph_is_configured()):
        df = _apply_overlay(df)
    _CACHE["initiatives"] = df
    _CACHE["_ts"] = time.time()
    return df.copy()


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    html_re = re.compile(r"<[^>]+>")
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).apply(lambda x: html_re.sub("", x).strip())
        df[col] = df[col].replace({"nan": "", "None": "", "0": ""})

    for col in ["forecasted_cost", "realized_cost", "forecasted_revenue",
                "realized_revenue", "forecasted_ebitda", "realized_ebitda"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_currency)

    if "pct_complete" in df.columns:
        df["pct_complete"] = df["pct_complete"].apply(
            lambda x: parse_pct(str(x)) if pd.notna(x) else None)

    for col in ["start_date", "target_completion", "revised_completion",
                "actual_completion", "benefit_start_date"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: parse_date(str(x)) if pd.notna(x) else None)

    if "status" in df.columns:
        df["status"] = df["status"].str.strip()
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)

    # Hierarchy columns must always exist so the roll-up is source-agnostic.
    if "task_type" not in df.columns:
        df["task_type"] = TYPE_INITIATIVE          # untyped legacy rows = Initiative
    else:
        df["task_type"] = df["task_type"].replace("", TYPE_INITIATIVE).fillna(TYPE_INITIATIVE)
    if "parent_id" not in df.columns:
        df["parent_id"] = ""
    # Normalize parent_id to a clean string id ("26.0" -> "26", NaN -> "").
    df["parent_id"] = (df["parent_id"].fillna("").astype(str)
                       .str.replace(r"\.0$", "", regex=True).str.strip()
                       .replace({"nan": "", "None": ""}))
    return df


def _apply_overlay(df: pd.DataFrame) -> pd.DataFrame:
    """Overlay staged edits, drop soft-deletes, and append staged new rows."""
    edits = _load_edits()
    if not edits:
        return df

    new_rows = edits.pop("_new_", {}) if isinstance(edits.get("_new_"), dict) else {}

    drop_ids = []
    for item_id, fields in edits.items():
        if not isinstance(fields, dict):
            continue
        mask = df["id"].astype(str) == str(item_id) if "id" in df.columns else pd.Series([], dtype=bool)
        if fields.get("_deleted"):
            drop_ids.append(str(item_id))
            continue
        if mask.any():
            for col, val in fields.items():
                if col.startswith("_"):
                    continue
                if col in df.columns:
                    df.loc[mask, col] = val

    if drop_ids and "id" in df.columns:
        df = df[~df["id"].astype(str).isin(drop_ids)]

    if new_rows:
        df = pd.concat([df, pd.DataFrame(list(new_rows.values()))], ignore_index=True)
    return df


# ── Writes ──────────────────────────────────────────────────────────────────
_GRAPH_DATE_FIELDS = {"start_date", "target_completion", "revised_completion",
                      "actual_completion", "benefit_start_date"}


def _iso_date(v):
    """Format a date for the List: ISO 8601 at noon UTC (noon avoids the date
    rolling back a day across US time zones). Accepts a date, a 'YYYY-MM-DD' HTML
    date input, or common US formats. None if unparseable."""
    from datetime import date as _date, datetime as _dt
    if isinstance(v, _date):                     # date (and datetime subclass)
        return v.strftime("%Y-%m-%dT12:00:00Z")
    s = str(v).strip()
    if not s:
        return None
    if "T" in s:                                 # already ISO
        s = s.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return _dt.strptime(s, fmt).strftime("%Y-%m-%dT12:00:00Z")
        except ValueError:
            continue
    return None


def _to_graph_fields(fields: dict) -> dict:
    """Map internal field names -> SharePoint columns for write-back, converting
    each value to what the List stores: dates as ISO 8601, and % Complete as a
    0-1 fraction (the app works in 0-100). Empty / unmapped values are dropped."""
    out = {}
    for k, v in fields.items():
        if k.startswith("_") or k not in INTERNAL_TO_GRAPH:
            continue
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        if k in _GRAPH_DATE_FIELDS:
            v = _iso_date(v)
            if v is None:
                continue
        elif k == "pct_complete":
            try:
                v = round(float(v) / 100.0, 4)
            except (TypeError, ValueError):
                continue
        out[INTERNAL_TO_GRAPH[k]] = v
    return out


def _live_write(sp_id, fields: dict) -> bool:
    """Push an update to the List via Graph, mapping internal -> SharePoint
    column names. Returns True on success. Only reached when writes are enabled."""
    graph_fields = _to_graph_fields(fields)
    if not graph_fields:
        return False
    from data.graph_client import get_graph_client
    get_graph_client().update_item(str(sp_id), graph_fields)
    return True


def update_initiative(item_id: str, fields: dict, sp_id=None) -> bool:
    """True on success. On failure the reason is logged AND kept in last_error()
    so the UI can show it - a failed save must never look like a success."""
    try:
        if settings.LIST_WRITE_ENABLED and settings.graph_is_configured() and sp_id:
            _live_write(sp_id, fields)
        else:
            edits = _load_edits()
            edits.setdefault(str(item_id), {})
            edits[str(item_id)].update({k: v for k, v in fields.items() if k != "id"})
            _save_edits(edits)
        clear_cache()
        _set_error(None)
        return True
    except Exception as e:
        log.exception("update_initiative(%s) failed", item_id)
        _set_error(f"{type(e).__name__}: {e}")
        return False


def create_initiative(fields: dict) -> bool:
    try:
        if settings.LIST_WRITE_ENABLED and settings.graph_is_configured():
            from data.graph_client import get_graph_client
            get_graph_client().create_item(_to_graph_fields(fields))
        else:
            new_id = f"new_{uuid.uuid4().hex[:8]}"
            edits = _load_edits()
            edits.setdefault("_new_", {})
            edits["_new_"][new_id] = {**fields, "id": new_id}
            _save_edits(edits)
        clear_cache()
        return True
    except Exception:
        return False


def create_task(parent_id, fields: dict, owner: str, creator: str) -> bool:
    """Create a Task row under a parent Initiative. Used by SLT and by Leaders
    assigning work to their team. Stores task_type=Task + parent_id so it rolls
    up to the parent."""
    payload = {
        **fields,
        "task_type":  TYPE_TASK,
        "parent_id":  str(parent_id),
        "owner":      owner,
        "created_by": creator,
    }
    return create_initiative(payload)


def delete_initiative(item_id: str, sp_id=None) -> bool:
    """Caller must verify sponsor permission before calling this."""
    try:
        if settings.LIST_WRITE_ENABLED and settings.graph_is_configured() and sp_id:
            from data.graph_client import get_graph_client
            get_graph_client().delete_item(str(sp_id))
        else:
            edits = _load_edits()
            edits.setdefault(str(item_id), {})
            edits[str(item_id)]["_deleted"] = True
            _save_edits(edits)
        clear_cache()
        return True
    except Exception:
        return False


# ── Sub-initiatives (TM task layer, local JSON) ─────────────────────────────
def load_sub_initiatives() -> pd.DataFrame:
    try:
        p = Path(settings.SUB_INITIATIVES_PATH)
        if p.exists():
            return pd.read_json(p)
    except Exception:
        pass
    return pd.DataFrame(columns=[
        "id", "parent_id", "name", "description", "owner", "status",
        "pct_complete", "due_date", "created_by", "next_action", "blockers",
    ])


def save_sub_initiatives(df: pd.DataFrame):
    p = Path(settings.SUB_INITIATIVES_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(p, orient="records", date_format="iso", indent=2)
