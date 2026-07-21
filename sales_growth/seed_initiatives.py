"""
sales_growth/seed_initiatives.py
Create the 12 consolidated Sales Growth initiatives (and their 90-day + year-one
tasks) in the live Strategic Initiatives List, linked parent -> child via Parent ID.

SAFETY:
  - DRY RUN by default: prints exactly what it would create and validates the field
    mapping, but writes NOTHING. Add --commit to actually write to the List.
  - Refuses to run if any of the 12 initiative names already exist (no double-seed).
  - Run from the SLT repo root so `data`/`config` import cleanly:
        python -m sales_growth.seed_initiatives            # dry run
        python -m sales_growth.seed_initiatives --commit   # writes to the List
"""
import sys, argparse
from datetime import datetime

from data.graph_client import get_graph_client
from data.loader import _to_graph_fields, load_initiatives
from data.models import TYPE_INITIATIVE, TYPE_TASK
from sales_growth.plan_data import PLAN, PLAN_START

STAMP = f"Sales Growth seed {datetime.today().strftime('%Y-%m-%d')}"


def _ini_fields(i):
    return {
        "task_type": TYPE_INITIATIVE, "name": i["name"], "sponsor": i["sponsor"],
        "owner": i["owner"], "region": i["region"], "category": "BOD",
        "priority": i["priority"],
        "description": f"{i['desc']}  |  KPI: {i['kpi']}  |  Contributors: {', '.join(i['contributors'])}",
        "status": "Not Started", "pct_complete": 0,
        "next_action": "DECISION: " + i["decisions"][0],
        "start_date": PLAN_START, "target_completion": i["target"],
        "forecasted_revenue": i["rev"], "forecasted_ebitda": i["ebitda"],
        "last_updated_by": STAMP,
    }


def _task_fields(i, name, phase, due):
    return {
        "task_type": TYPE_TASK, "name": name, "sponsor": i["sponsor"], "owner": i["owner"],
        "region": i["region"], "category": "BOD", "priority": i["priority"],
        "description": "90-day action" if phase == "90d" else "Year-one milestone",
        "status": "Not Started", "pct_complete": 0,
        "start_date": PLAN_START, "target_completion": due, "last_updated_by": STAMP,
        # parent_id filled in once the parent is created
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="actually write to the List")
    args = ap.parse_args()

    # guard: no double-seed
    existing = set(load_initiatives(force=True)["name"].dropna().astype(str))
    clash = [i["name"] for i in PLAN if i["name"] in existing]
    if clash:
        print("ABORT - these initiative names already exist on the List:")
        for c in clash: print("   -", c)
        print("Delete them first or rename, then re-run.")
        return 1

    n_ini = len(PLAN); n_task = sum(len(i["tasks"]) for i in PLAN)
    mode = "COMMIT (writing to the live List)" if args.commit else "DRY RUN (no writes)"
    print(f"=== Sales Growth seed :: {mode} ===")
    print(f"Will create {n_ini} initiatives + {n_task} tasks = {n_ini + n_task} rows\n")

    gc = get_graph_client() if args.commit else None
    for i in PLAN:
        gf = _to_graph_fields(_ini_fields(i))
        if args.commit:
            created = gc.create_item(gf)
            pid = created.get("id")
            if not pid:  # fallback: find the row we just made
                rows = get_graph_client().get_items()
                pid = next((r.get("id") or r.get("_sp_item_id") for r in rows
                            if str(r.get("Title", "")) == i["name"]), None)
            print(f"[created] {i['code']} {i['name']}  -> ID {pid}")
        else:
            pid = f"<{i['code']}-id>"
            print(f"[dry] INITIATIVE {i['code']}: {i['name']}")
            print(f"       sponsor={i['sponsor']} owner={i['owner']} region={i['region']} "
                  f"rev={i['rev']} ebitda={i['ebitda']} -> {len(gf)} mapped fields")
        for name, phase, due in i["tasks"]:
            tf = _to_graph_fields(_task_fields(i, name, phase, due))
            tf["ParentID"] = int(pid) if (args.commit and str(pid).isdigit()) else pid
            if args.commit:
                gc.create_item(tf)
            else:
                print(f"        - TASK ({phase}, due {due}): {name[:70]}")
    print(f"\n{'DONE - rows written.' if args.commit else 'DRY RUN complete - no writes. Re-run with --commit to write.'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
