"""
sales_growth/plan_data.py
Single source of truth for the consolidated Sales Growth plan (the 12 initiatives
from the July 2026 SLT workshop). Feeds three outputs so they never drift:
  - build_excel.py  -> an .xlsx that matches the Strategic Initiatives List columns
  - seed_initiatives.py -> creates the Initiative + Task rows in the live List (Graph)
  - build_ppt.py    -> the built-out consolidated deck (decisions + 90-day/year actions)

Region aligns to the List's existing values ("Corp" for company-wide, "UK" for EMEA).
Category is BOD (Board / SLT) for all. Financials are FULL DOLLARS.
"""

PLAN_START = "2026-07-21"
# due-date buckets used across the plan
D_AUG, D_SEP, D_OCT = "2026-08-31", "2026-09-30", "2026-10-31"
D_YE = "2026-12-31"          # end of this year (near-free moves)
D_Q1, D_Q2 = "2027-03-31", "2027-06-30"   # year-one milestones

# Owners are the real SLT names (roles.yaml). Task owner defaults to the initiative
# Owner; the suggested function is named in the task title for easy reassignment.
PLAN = [
  # ============================ TIER A - CORE PLAYS ============================
  dict(
    code="A1", tier="Core Play", priority="1", region="Corp",
    name="Own the Account: Sell Deep to Existing Customers",
    sponsor="Brian Beth", owner="Ty Rhoad",
    contributors=["Chad Abrahamson","Nick Zager","Paul Reidy","Joe Stodola"],
    rev=6_500_000, ebitda=None, target="2027-06-30",
    kpi="Families-per-account at the top-40 nationals; within-core whitespace $ closed (target ~$2.5M at buying rate)",
    desc="Get every national account to the WM model (all 5 core families). AI maps the whitespace, names the next part, and automates the push. Range $5-8M by Yr-3.",
    decisions=[
      "Approve the national-account coverage model and a national quarterback for the 4 split haulers (WM, Republic, Waste Connections, GFL).",
      "Approve comp credit for families-per-account (ties to C10).",
    ],
    tasks=[
      ("Expand the AI cross-sell recommender from the built CO compactor worklist to all core families (IT / DemandPulse)","90d",D_SEP),
      ("Rank the top-40 national operators by within-core whitespace $ and assign owners (National Accounts)","90d",D_AUG),
      ("Launch family-gap pursuit at WM and Athens (marquee bottoms gap ~$198K) (Sales)","90d",D_OCT),
      ("National quarterback covering all 4 split haulers; families-per-account rising at the top-40","year",D_Q1),
      ("Close the first ~$2.5M of within-core whitespace at each account's own buying rate","year",D_Q2),
    ]),
  dict(
    code="A2", tier="Core Play", priority="1", region="Corp",
    name="Formalize the PM Contract Channel (Service)",
    sponsor="Brian Beth", owner="Ty Rhoad",
    contributors=["Chad Abrahamson","Joe Stodola","Nick Zager"],
    rev=4_000_000, ebitda=None, target="2027-06-30",
    kpi="Current service customers on a signed 3-tier PM agreement; recurring PM revenue and renewal rate",
    desc="Formalize our CURRENT service business into a true PM Contract Channel: a three-tier program (Bronze/Silver/Platinum) of scheduled preventive maintenance + wear-parts coverage that turns episodic service POs into predictable recurring revenue. No SaaS or machine-monitoring in this scope. Revised target ~$4M (down from $8-12M) - see the plan note.",
    decisions=[
      "Approve the FSM PM contract motion and the three-tier structure (Bronze/Silver/Platinum: PM cadence + priority response + wear-parts coverage).",
      "Confirm the revised revenue target and which current service customers convert first + the tier pricing.",
    ],
    tasks=[
      ("Design the three-tier PM program and tier pricing on the current service book (Service / FSM)","90d",D_SEP),
      ("Build the conversion list from the current service book, starting with the 255 both-buyers and the retail service accounts (Service)","90d",D_AUG),
      ("Sign the first PM agreements including H-E-B (Service)","90d",D_OCT),
      ("A meaningful share of the current service book on signed 3-tier PM agreements","year",D_Q2),
      ("PM renewal + wallet-uplift motion running; recurring PM revenue building","year",D_Q2),
    ]),
  dict(
    code="A3", tier="Core Play", priority="1", region="Corp",
    name="Never Miss the Demand: CX + AI Engine",
    sponsor="Chad Abrahamson", owner="Chad Abrahamson",
    contributors=["Brian Beth","Joe Stodola","Paul Reidy","Ty Rhoad"],
    rev=12_000_000, ebitda=None, target="2026-12-31",
    kpi="Call answer rate 63.5% -> 85%; quote response hours -> minutes; win-back $ reactivated (of the ~$22.6M leak)",
    desc="Capture and convert every inbound and work the save / win-back lists. RingCX/ACE + Front + DemandPulse, plus a service-coordinator AI. Direct $1-3M and powers $10-25M of retention.",
    decisions=[
      "Approve ACE seats + Front quote-inbox extension (~$15-30K/yr total).",
      "Turn on the <1hr SLA rule and the after-hours AI receptionist; name the save-desk owner.",
    ],
    tasks=[
      ("Buy ACE seats, extend Front to the quote inbox, wire the ACE summary into the CRM (IT / Sales Ops)","90d",D_AUG),
      ("Turn on automatic callback + skills routing to move pickup toward 85% (Sales Ops)","90d",D_SEP),
      ("Deploy the built Account Health churn worklist + reorder / win-back lists into Front as the daily save-desk feed (IT)","90d",D_SEP),
      ("Answer rate 63.5% -> 85%; quote response from hours to minutes","year",D_Q1),
      ("Cut the ~$22.6M core leak by a third via win-back + auto-replenish","year",D_Q2),
    ]),

  # ========================= TIER B - EXPANSION BETS =========================
  dict(
    code="B4", tier="Expansion Bet", priority="2", region="Corp",
    name="Digital and Ecommerce Channel",
    sponsor="Brian Beth", owner="Paul Reidy",
    contributors=["Joe Stodola"],
    rev=2_000_000, ebitda=None, target="2027-06-30",
    kpi="Online-sourced pipeline $ and orders; marketplace GMV (target to validate in Q1)",
    desc="An online parts marketplace plus direct container sales, built on our existing SEO strength and web platform (we already rank #2 for 'dumpsters for sale'). Additive, not a pivot.",
    decisions=[
      "Resolve the OEM channel-conflict policy for direct container sales.",
      "Build vs partner: marketplace scope and the regional OEM fulfillment partners.",
    ],
    tasks=[
      ("Business case + channel-conflict guardrails for online container sales (Marketing)","90d",D_SEP),
      ("Stand up a geo-targeted dumpster storefront pilot on the existing web + SEO/PPC (Marketing)","90d",D_OCT),
      ("Scope the parts-marketplace MVP (ecommerce + AI parts lookup) (IT / Marketing)","90d",D_OCT),
      ("Regional OEM fulfillment partners signed; first online-sourced revenue","year",D_Q2),
      ("Marketplace MVP live with a third-party-seller pilot","year",D_Q2),
    ]),
  dict(
    code="B5", tier="Expansion Bet", priority="2", region="Corp",
    name="Chutes and Building-Waste Infrastructure",
    sponsor="Brian Beth", owner="Ty Rhoad",
    contributors=["Joe Stodola","Nick Zager"],
    rev=5_000_000, ebitda=None, target="2027-06-30",
    kpi="Midland book YoY recovery; chute lifecycle service contracts signed (target to size in Q1)",
    desc="Scale Midland, own the chute lifecycle (design to replacement), control distribution, and target the commercial-building segment. Midland carries 35%+ EBITDA and is under-sold.",
    decisions=[
      "Buy vs build chute manufacturing capacity; distributor-exclusivity policy.",
      "Which building segments to target first (apartments, hospitals, universities, hotels).",
    ],
    tasks=[
      ("Size the Midland book recovery + the chute-lifecycle service opportunity (Ops / Finance)","90d",D_SEP),
      ("Require distributors to sell Midland chutes + compactors; add under-penetrated distributors (Sales)","90d",D_OCT),
      ("Stand up the chute-lifecycle service offer (inspect, clean, repair, modernize) on the tech network (Service)","90d",D_OCT),
      ("National end-to-end chute lifecycle offer live","year",D_Q2),
      ("Evaluate a chute-manufacturing acquisition target (ties to C12)","year",D_Q2),
    ]),
  dict(
    code="B6", tier="Expansion Bet", priority="2", region="Corp",
    name="Manufacturing and Product Expansion",
    sponsor="Joe Stodola", owner="Paul Reidy",
    contributors=["Nick Zager","Chad Abrahamson"],
    rev=4_000_000, ebitda=None, target="2027-06-30",
    kpi="California bottoms share; blow-molded lid share recapture $ (Hauler $7M + OEM $4M pools)",
    desc="Duraflex and clamshell lids, California and regional bottoms manufacturing, and depot optimization to win on landed cost and enter new geographies. The CA bottoms market alone is ~$18.9M/yr.",
    decisions=[
      "Import vs manufacture California / regional bottoms; depot investment (FL, PNW, Canada).",
      "Qualify and field-test the clamshell lid; blow-molded market entry and trust win-back.",
    ],
    tasks=[
      ("Size the California bottoms market and demand for standard vs custom (Marketing)","90d",D_SEP),
      ("Optimize the FL depot as a competitive advantage; regionally landed casters (Ops)","90d",D_OCT),
      ("Qualify and field-test the Duraflex clamshell; win-back-trust plan (Ops / Quality)","90d",D_OCT),
      ("PNW depot / bottoms-manufacturing business case decided (Parker)","year",D_Q1),
      ("Blow-molded lid share recapture underway (California + OEM conversions)","year",D_Q2),
    ]),
  dict(
    code="B7", tier="Expansion Bet", priority="3", region="Corp",
    name="Equipment and Rental Strategy",
    sponsor="Ty Rhoad", owner="Ty Rhoad",
    contributors=["Brian Beth","Joe Stodola"],
    rev=3_000_000, ebitda=None, target="2027-06-30",
    kpi="Repeatable-equipment units sold; rental utilization; equipment replacement pipeline (target to size)",
    desc="Smaller repeatable equipment sales, rentals to shorten the buying decision, replacement cycles, and recombining rentals with service. Reduce dependence on large one-off projects.",
    decisions=[
      "Rental model: own fleet vs partner.",
      "Recombine Rentals and Services (Joe's big idea) or keep separate.",
    ],
    tasks=[
      ("Define the smaller-repeatable-equipment target segments + regional distribution partners (Sales)","90d",D_SEP),
      ("Stand up rental options to shorten the sales decision (Sales / Ops)","90d",D_OCT),
      ("Fix the equipment-sales pipeline owner gap (MRF / organics has no driver) (Sales)","90d",D_OCT),
      ("Repeatable-equipment motion producing a steady replacement pipeline","year",D_Q2),
      ("Rentals + Services recombination decision and plan","year",D_Q1),
    ]),
  dict(
    code="B8", tier="Expansion Bet", priority="3", region="UK",
    name="New Geographies: EMEA Liquid Waste",
    sponsor="Joe Stodola", owner="Paul Reidy",
    contributors=["Brian Beth"],
    rev=2_000_000, ebitda=None, target="2027-06-30",
    kpi="EMEA export revenue; distribution partners signed; make-vs-export decision (target to size)",
    desc="Manufacture and sell liquid-waste products in EMEA and grow export sales on the existing portfolio, then build European distribution and marketing.",
    decisions=[
      "EMEA: export-first vs manufacture liquid-waste products in Europe.",
      "Evaluate a Canada / GTA depot as an adjacent geography.",
    ],
    tasks=[
      ("Grow export sales on the existing product portfolio (Sales)","90d",D_SEP),
      ("Build the EMEA distribution + marketing plan (Marketing)","90d",D_OCT),
      ("EMEA liquid-waste manufacturing / distribution decision","year",D_Q2),
      ("Evaluate the Canada / GTA depot potential","year",D_Q2),
    ]),
  dict(
    code="B9", tier="Expansion Bet", priority="2", region="Corp",
    name="Grow Under-Marketed Lines and Channels",
    sponsor="Paul Reidy", owner="Paul Reidy",
    contributors=["Chad Abrahamson","Ty Rhoad","Nick Zager"],
    rev=4_000_000, ebitda=None, target="2027-06-30",
    kpi="Baler-parts penetration of the 418 runners; OEM build-share (casters/hardware); cylinder-reman volume",
    desc="Baler parts, baling wire and relines (geo-targeted to corrugator/DC density), cylinder reman, ozone and absorbents, and the independent-OEM channel. Range $3-6M organic.",
    decisions=[
      "OzonePro relaunch go / no-go.",
      "OEM-channel investment vs the Wastequip (~$8.65M) concentration risk.",
    ],
    tasks=[
      ("Push baler parts into the 418 baler-runners buying zero from us (Sales)","90d",D_SEP),
      ("Scale the Lake Mills cylinder-reman exchange into 1,000+ operators (Sales / Service)","90d",D_OCT),
      ("Grow independent-OEM build-share (casters, hardware) across the 57 OEMs (Sales)","90d",D_OCT),
      ("OzonePro relaunch across chutes + core waste + recurring service","year",D_Q2),
      ("Baling wire and relines geo-expansion (corrugator / DC density)","year",D_Q2),
    ]),

  # ============================ TIER C - ENABLERS ============================
  dict(
    code="C10", tier="Enabler", priority="1", region="Corp",
    name="Sales Force and Comp Redesign",
    sponsor="Ty Rhoad", owner="Ty Rhoad",
    contributors=["Chad Abrahamson","Joe Stodola","Paul Reidy","Brian Beth"],
    rev=2_000_000, ebitda=None, target="2026-12-31",
    kpi="Comp plan live; % of variable tied to recurring/retention; rep selling-time up from 15-20%",
    desc="Fix coverage (A vs B/C accounts), pair reps with technical experts, arm technicians to sell, and re-weight comp toward recurring, retention, and attach. The make-or-break enabler.",
    decisions=[
      "Comp design: A Re-weight now, then B Overlay, then C Scorecard.",
      "Coverage model: CX/AI on B/C accounts; paired rep + technical-expert selling.",
    ],
    tasks=[
      ("Adopt Design A (budget-neutral re-weight toward recurring + retention) (CRO / CFO)","90d",D_SEP),
      ("Add the equipment-rep attach bonus + a first-year contract-ARR slice (CRO)","90d",D_OCT),
      ("Stand up the paired rep + technical-expert selling model (WM 58 open locations pilot) (Sales / Marketing)","90d",D_OCT),
      ("Move to Design B overlay as contracts sign; retention as its own quota","year",D_Q1),
      ("CX / AI covering B/C accounts; rep selling-time up from 15-20%","year",D_Q2),
    ]),
  dict(
    code="C11A", tier="Enabler", priority="1", region="Corp",
    name="Pricing Strategy Revamp",
    sponsor="Paul Reidy", owner="Paul Reidy",
    contributors=["Nick Zager","Chad Abrahamson"],
    rev=2_780_000, ebitda=3_000_000, target="2026-12-31",
    kpi="Price-book coverage of the 3,022 unpriced sellers; leakage recaptured $ (of $7.71M); GM added",
    desc="Consolidate 40+ overlapping customer books into a clean tier set, enforce it, and cover the business that has no price book. Adds $3-6M of gross margin from our own base and defends revenue (governed accounts churn far less). Funds the growth.",
    decisions=[
      "Pricing enforcement mandate and owner; rebates as structured tiers vs discretionary discounting.",
      "Sequence: consolidate the books first, then expand coverage to the unpriced sellers.",
    ],
    tasks=[
      ("Consolidate 40+ books into a clean tier set; name the enforcement owner (Pricing)","90d",D_SEP),
      ("Enforce the corrected book to recapture ~$2.78M of the $7.71M leakage (Pricing)","90d",D_OCT),
      ("Cover the 3,022 unpriced sellers ($20.4M) with a governing price book (Pricing / IT)","90d",D_OCT),
      ("Price-book coverage near 100%; churn on the ungoverned base falling","year",D_Q2),
      ("Structured tier-rebate program live (share gains without margin leakage)","year",D_Q1),
    ]),
  dict(
    code="C11B", tier="Enabler", priority="2", region="Corp",
    name="Clare to Elgin Consolidation",
    sponsor="Nick Zager", owner="Nick Zager",
    contributors=["Joe Stodola"],
    rev=None, ebitda=None, target="2027-06-30",
    kpi="Cost-out analysis validates (or not) ~$0.24M net EBITDA and ~2-yr payback; go / no-go decision",
    desc="Consolidate the Clare lid-sheet extrusion into Elgin. FIRST validate with a cost-out analysis (Clare-to-Elgin freight ~$244K + the outside Tocco operator ~$157K vs higher Elgin rent) before any build-out. Proceed only if the ~$0.24M net EBITDA and ~2-yr payback hold.",
    decisions=[
      "Does the cost-out analysis confirm the consolidation makes sense (savings net of higher Elgin rent)?",
      "If validated, approve the Elgin build-out and the optional LD reprice; if not, park it.",
    ],
    tasks=[
      ("Run the Clare-to-Elgin cost-out analysis to confirm it makes sense (~$244K freight + ~$157K operator vs Elgin rent) (Finance / Ops)","90d",D_SEP),
      ("Go / no-go decision on the consolidation based on the analysis (CFO)","90d",D_OCT),
      ("If validated: execute the Elgin build-out (~$0.24M EBITDA, ~2-yr payback)","year",D_Q2),
      ("Evaluate the LD reprice option to chase back lost LD share","year",D_Q2),
    ]),
  dict(
    code="C12", tier="Enabler", priority="2", region="Corp",
    name="Accelerate: M&A",
    sponsor="Brian Beth", owner="Nick Zager",
    contributors=["Chad Abrahamson","Joe Stodola"],
    rev=None, ebitda=None, target="2027-06-30",
    kpi="LOIs issued; deals closed; revenue and EBITDA acquired (slate soft-vetted, to be sized in diligence)",
    desc="Service roll-ups, chute manufacturing, cylinder, absorbents and organics tuck-ins, and a national rental book. The accelerant on top of the organic plays; targets are soft-vetted only and get sized in diligence.",
    decisions=[
      "Approve the M&A mandate for the soft-vetted slate.",
      "Sequence the Tier-A targets (Power Knot, Apex, Andela, a cylinder tuck-in).",
    ],
    tasks=[
      ("Approach the Tier-A slate with the vetting pack (Corp Dev)","90d",D_SEP),
      ("Prioritize the service roll-ups + chute-mfg targets that plug into A2 and B5 (Corp Dev)","90d",D_OCT),
      ("LOIs on 2-3 on-strategy targets","year",D_Q1),
      ("First close(s) adding revenue + EBITDA into the plan","year",D_Q2),
    ]),
]


def summary():
    n_tasks = sum(len(i["tasks"]) for i in PLAN)
    rev = sum(i["rev"] or 0 for i in PLAN)
    return dict(initiatives=len(PLAN), tasks=n_tasks, total_forecast_rev=rev)


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=2))
    for i in PLAN:
        print(f"{i['code']:4} {i['name'][:44]:44} {i['sponsor']:16}/{i['owner']:16} "
              f"${(i['rev'] or 0)/1e6:5.1f}M  {len(i['tasks'])} tasks")
