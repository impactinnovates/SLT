"""
data/source.py
Single entry point for "where does initiative data come from".

The SharePoint List is the only source of truth. There is deliberately no local
fallback: a stale CSV that silently stands in for the List looks identical to
live data on screen, and the SLT would have no way to tell they were reading
last quarter's numbers. If Graph is not configured we raise instead.

Returns a DataFrame with the internal column names in data/models.py, so
everything downstream (pacing, roll-up, views) stays source-agnostic.
"""
import pandas as pd

from config import settings
from data.models import GRAPH_MAP


def source_label() -> str:
    """'live' when the List is reachable; 'unconfigured' when GRAPH_* is unset."""
    return "live" if settings.graph_is_configured() else "unconfigured"


def fetch_initiatives() -> pd.DataFrame:
    """Base initiatives DataFrame (unenriched, no edit overlay applied)."""
    if not settings.graph_is_configured():
        raise RuntimeError(
            "The SharePoint List is not configured, so there is no data to show. "
            "Set GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, SITE_ID "
            "and LIST_ID (see README.md / AZURE_RUNBOOK.md)."
        )
    return _from_graph()


def _from_graph() -> pd.DataFrame:
    from data.graph_client import get_graph_client
    rows = get_graph_client().get_items()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # The SharePoint item id is the write-back key; surface it as sp_id.
    if "_sp_item_id" in df.columns:
        df["sp_id"] = df["_sp_item_id"]
    out = df.rename(columns={k: v for k, v in GRAPH_MAP.items() if k in df.columns})
    # A Hyperlink column comes back as {"Url":..., "Description":...}. Flatten it to
    # the URL string now, before _clean_df stringifies object columns into reprs
    # (which would leave the edit form showing "{'Url': ...}"). Write-back re-wraps
    # the string into the dict shape the column needs.
    if "project_link" in out.columns:
        out["project_link"] = out["project_link"].apply(
            lambda v: v.get("Url", "") if isinstance(v, dict) else v)
    # The List stores % Complete as a 0-1 fraction; the rest of the app works in
    # 0-100. Scale up on read so pacing, progress bars and the form all agree.
    if "pct_complete" in out.columns:
        pct = pd.to_numeric(out["pct_complete"], errors="coerce")
        out.loc[pct.notna(), "pct_complete"] = pct[pct.notna()] * 100
    return out
