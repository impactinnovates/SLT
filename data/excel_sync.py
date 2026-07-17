"""
data/excel_sync.py
Sync a shared Excel tracker into the List.

The 2026 Cost Takeout Tracker holds each savings action tagged with a List ID
(column AV) and its FY26 Actual Realized figure (column X, in $ thousands). This
reads the sheet via Graph by its stable file id, groups by List ID (summing rows
that share one), and writes to each initiative:
  - Realized EBITDA = sum(X) * 1000
  - % Complete      = Realized / Budget (forecasted EBITDA), real/uncapped
  - Last Updated By = "Cost Takeout Sync <timestamp>"  (so we can see when it ran)

Safe by default: compute_updates() only READS. Writes happen only via
apply_updates() (the "Sync now" button, or the CLI with --apply).

CLI:
  python -m data.excel_sync              # dry-run, prints before -> after
  python -m data.excel_sync --apply      # write all
  python -m data.excel_sync --apply --only 118   # write a single id (supervised test)
"""
import sys
import json
import requests
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from config import settings
from data.loader import load_initiatives, clear_cache
from utils import rollup
from data.models import INTERNAL_TO_GRAPH

GRAPH = "https://graph.microsoft.com/v1.0"
CONFIG = Path(__file__).parent.parent / "config" / "excel_sync.yaml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


# ── Synced-state snapshot ────────────────────────────────────────────────────
# The edit form must lock a field ONLY when it is genuinely driven by the tracker.
# The truthful signal is "the last full sync actually wrote this id", so we record
# that here after every full apply and the app reads it back.
def _synced_fields(cfg: dict) -> list:
    """Internal field names the sync owns (realized + budget + %)."""
    w = cfg["writes"]
    return [w["realized_field"], w["budget_field"], w["pct_field"]]


def _record_synced_state(results: list, cfg: dict):
    ids = sorted({str(r["id"]) for r in results if r.get("status") == "updated"},
                 key=lambda s: int(s) if s.isdigit() else 0)
    state = {
        "ids": ids,
        "fields": _synced_fields(cfg),
        "sources": [s["name"] for s in cfg.get("sources", [])],
        "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    try:
        p = Path(settings.SYNCED_STATE_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass  # locking is a convenience; never let a write-snapshot failure break the sync


def synced_state() -> dict:
    """What the last full sync touched: {ids, fields, sources, at}. Empty when the
    sync has never run, so nothing is locked by default."""
    try:
        p = Path(settings.SYNCED_STATE_PATH)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"ids": [], "fields": [], "sources": [], "at": None}


def _col(letter: str) -> int:
    i = 0
    for ch in letter.upper():
        i = i * 26 + (ord(ch) - 64)
    return i - 1


def _num(v):
    try:
        f = float(v)
        return None if f != f else f      # treat NaN as missing (NaN != NaN)
    except (TypeError, ValueError):
        return None


def _read_sheet(src: dict):
    from data.graph_client import get_graph_client
    h = {"Authorization": f"Bearer {get_graph_client()._token()}"}
    url = (f"{GRAPH}/drives/{src['drive_id']}/items/{src['item_id']}"
           f"/workbook/worksheets/{src['sheet']}/usedRange?$select=values,text")
    r = requests.get(url, headers=h, timeout=60)
    r.raise_for_status()
    j = r.json()
    return j["values"], j["text"]


def compute_updates(cfg: dict | None = None):
    """READ-ONLY. Returns (updates, cfg). Each update dict carries old + new
    values so the UI/CLI can show a before -> after diff before anything writes."""
    cfg = cfg or load_config()
    w = cfg["writes"]

    # Group realized (value_column) and budget (budget_column) by List ID across
    # all sources, summing rows that share an id.
    groups = defaultdict(lambda: {"realized": 0.0, "budget": 0.0, "n": 0})
    for src in cfg["sources"]:
        values, text = _read_sheet(src)
        hdr = next((n for n, r in enumerate(text)
                    if any("strategic initiative" in str(c).lower() for c in r)), 0)
        ic, vc = _col(src["id_column"]), _col(src["value_column"])
        bc = _col(src["budget_column"]) if src.get("budget_column") else None
        mult = src.get("multiplier", 1)
        for r in values[hdr + 1:]:
            if len(r) <= ic:
                continue
            lid = _num(r[ic])
            if lid is None:
                continue
            g = groups[str(int(lid))]
            if len(r) > vc:
                g["realized"] += (_num(r[vc]) or 0) * mult
            if bc is not None and len(r) > bc:
                g["budget"] += (_num(r[bc]) or 0) * mult
            g["n"] += 1

    inits, _ = rollup.split_hierarchy(load_initiatives())
    by_id = {str(x["id"]): x for _, x in inits.iterrows()}
    stamp = f"{w['stamp_label']} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    cap = w.get("pct_cap")

    updates = []
    for key, g in groups.items():
        ini = by_id.get(key)
        realized = round(g["realized"])
        budget = round(g["budget"])            # Excel is source of truth for budget
        if budget > 0:
            pct = realized / budget
            if cap is not None:
                pct = min(pct, cap)
        else:
            pct = 1.0 if realized > 0 else 0.0  # $0 budget => all upside
        updates.append({
            "id": key, "found": ini is not None, "rows": g["n"],
            "name": (ini["name"] if ini is not None else "(id not in List)"),
            "realized_old": (ini.get(w["realized_field"]) if ini is not None else None),
            "realized_new": realized,
            "budget_old": (_num(ini.get(w["budget_field"])) if ini is not None else None),
            "budget_new": budget,
            "pct_old": (ini.get(w["pct_field"]) if ini is not None else None),
            "pct_new": pct, "stamp": stamp,
        })
    return sorted(updates, key=lambda u: int(u["id"])), cfg


def apply_updates(updates: list, cfg: dict, only: str | None = None) -> list:
    """WRITES to the List. Returns each update with a 'status'."""
    from data.graph_client import get_graph_client
    w = cfg["writes"]
    client = get_graph_client()
    results = []
    for u in updates:
        if only is not None and str(u["id"]) != str(only):
            continue
        if not u["found"]:
            results.append({**u, "status": "skipped (id not in List)"})
            continue
        fields = {
            INTERNAL_TO_GRAPH[w["realized_field"]]: u["realized_new"],
            INTERNAL_TO_GRAPH[w["budget_field"]]: u["budget_new"],   # Excel is source of truth
            INTERNAL_TO_GRAPH[w["stamp_field"]]: u["stamp"],
        }
        if u["pct_new"] is not None:
            fields[INTERNAL_TO_GRAPH[w["pct_field"]]] = round(u["pct_new"], 4)  # 0-1 fraction
        try:
            client.update_item(u["id"], fields)
            results.append({**u, "status": "updated"})
        except Exception as e:
            results.append({**u, "status": f"error: {str(e)[:120]}"})
    # Snapshot which ids are tracker-driven, but only on a FULL sync - a single-id
    # supervised test (--only) must not shrink the recorded set to one id.
    if only is None:
        _record_synced_state(results, cfg)
    clear_cache()
    return results


def _cli():
    apply = "--apply" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    updates, cfg = compute_updates()
    print(f"{'ID':>5} {'rows':>4} {'realized':>11} {'budget':>11} {'pct':>7}  name")
    for u in updates:
        pct = f"{u['pct_new']*100:.0f}%" if u["pct_new"] is not None else "-"
        print(f"{u['id']:>5} {u['rows']:>4} {u['realized_new']:>11,} {u['budget_new']:>11,} {pct:>7}  {u['name'][:38]}")
    if apply:
        print(f"\nAPPLYING{' (only ' + only + ')' if only else ''} ...")
        for r in apply_updates(updates, cfg, only=only):
            print(f"  {r['id']:>5}  {r['status']}")
    else:
        print("\ndry-run only. add --apply (optionally --only <id>) to write.")


if __name__ == "__main__":
    _cli()
