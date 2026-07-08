"""
data/source.py
Single entry point for "where does initiative data come from".

  graph_is_configured()  ->  live SharePoint List via app-only Graph
  otherwise              ->  the local CSV export (data/Strategic_Initiatives_2026.csv)

Both paths return a DataFrame with the same internal column names (see
data/models.py), so everything downstream (pacing, views) is source-agnostic.
The app runs fully today on the CSV and flips to live the moment the GRAPH_*
credentials + admin consent are in place — no code change required.

NOTE: GRAPH_MAP in models.py maps the List's *internal* column names to our
internal fields. Those internal names are currently best-guesses; the probe
(probe_list_connection.py) prints the real ones so we can reconcile GRAPH_MAP
before turning the live read path on for users.
"""
import pandas as pd

from config import settings
from data.models import CSV_MAP, GRAPH_MAP


def source_label() -> str:
    """'live' when reading the SharePoint List, 'csv' when on the local export."""
    return "live" if settings.graph_is_configured() else "csv"


def fetch_initiatives() -> pd.DataFrame:
    """Base initiatives DataFrame (unenriched, no edit overlay applied)."""
    if settings.graph_is_configured():
        return _from_graph()
    return _from_csv()


def _from_csv() -> pd.DataFrame:
    df = pd.read_csv(settings.CSV_PATH, encoding="utf-8-sig")
    return df.rename(columns={k: v for k, v in CSV_MAP.items() if k in df.columns})


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
    # The List stores % Complete as a 0-1 fraction; the rest of the app works in
    # 0-100. Scale up on read so pacing, progress bars and the form all agree.
    if "pct_complete" in out.columns:
        pct = pd.to_numeric(out["pct_complete"], errors="coerce")
        out.loc[pct.notna(), "pct_complete"] = pct[pct.notna()] * 100
    return out
