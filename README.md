# IEG Strategic Initiatives

Internal dashboard for SLT strategic initiatives. Flask + Jinja2 + HTMX, matching
the DemandPulse / SCP / Financial Dashboard stack. Microsoft Entra sign-in, role
layers (SLT / Leader / Member), and a live connection to the Strategic Initiatives
SharePoint List (with a local CSV fallback so it runs with zero cloud setup).

## Model

A two-level hierarchy in one List (`Task/Initiative` field), with roll-up:

```
Initiative  (SLT-owned, BOD-reported, financials)
   └── Task (assigned to a Leader; Parent ID -> initiative)  rolls up %/risk to the parent
          └── sub-task (a Leader may assign to their Members)
```

Roll-up: a parent shows rolled-up % complete and a risk flag if any child task is
Behind/Blocked; SLT can override the parent %. See `LIST_CHANGES.md` for the one
List column this needs (`Parent ID`).

## Quick start (local dev)

```
cd C:\Users\Chad\Downloads\Python\SLT
python app.py
```

Open http://127.0.0.1:8502. With no Entra vars set, the app runs **open** as a dev
SLT user, so every layer is viewable without a tenant.

The SharePoint List is the only data source: local dev still needs the `GRAPH_*`
vars in `.env` (see `.env.template`), and the app raises a clear error rather
than starting on stale data if they are missing.

Production (Azure App Service) runs `gunicorn -b 0.0.0.0:8502 wsgi:app`.

## Architecture

```
Microsoft Entra ID  ──(SSO, who you are)──▶  auth.py ──▶ role from config/roles.yaml
                                                              │  SLT / PM / TM
SharePoint List  ──(app-only Graph, service identity)──▶ data/graph_client.py
      │                                                       │
      └── not configured? ── data/source.py ──▶ local CSV ────┤
                                                              ▼
                                        data/loader.py (clean + edit overlay + writes)
                                                              ▼
                                        app.py (Flask routes, role scoping, HTMX)
                                                              ▼
                                        templates/*.html  (IEG-branded, static/brand.css)
```

- **Reads** go live automatically once `GRAPH_*` is configured (see `.env.template`).
- **Writes** stage in `data/edits.json` and only hit the List when
  `LIST_WRITE_ENABLED=true` — flipped on after the probe confirms the List's real
  internal column names and `GRAPH_MAP` (data/models.py) is reconciled.

## Connecting to the live List

1. Get IT to grant the app-only Graph permission — see
   [IT_REQUEST_graph_permission.md](IT_REQUEST_graph_permission.md).
2. Put `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` in `.env`.
3. Confirm the connection:
   ```
   python probe_list_connection.py
   ```
   It acquires a token, lists every List on the site (set `LIST_NAME` to the right
   one), and prints the real internal column names + a sample item.
4. Reconcile `GRAPH_MAP` in `data/models.py` with those internal names.
5. Set `LIST_WRITE_ENABLED=true` to write edits back to the List.

## Roles

Edit `config/roles.yaml` — matched against the signed-in Microsoft identity
(display name or email). No restart needed.

| Role | Access |
|------|--------|
| SLT    | All initiatives + tasks + financials + board report; create/assign; delete (if sponsor) |
| Leader | ONLY tasks they own or assigned to their team; never sees initiatives or financials; can create/assign sub-tasks |
| Member | ONLY tasks assigned to them; status/progress updates |

Visibility is enforced server-side - Leader/Member requests can never load
initiatives (verified: they get 403 on every SLT route). Locally (no SSO) use
`?as=SLT|Leader|Member` to preview each layer.

## Layout

```
app.py                  Flask app: routes, role scoping, HTMX write endpoints
wsgi.py                 gunicorn entry (wsgi:app)
auth.py                 Entra SSO; roles from roles.yaml; open in local dev
config/
  settings.py           env + config; graph_is_configured(); role helpers
  roles.yaml            user -> SLT/PM/TM
data/
  graph_client.py       app-only Microsoft Graph List client (read/write)
  source.py             live List or local CSV (one interface)
  loader.py             clean + edit overlay + write-back
  models.py             CSV/Graph field maps, parsers, status colors
utils/pacing.py         financial pacing engine (pure pandas)
components/financial_charts.py   Plotly figures
templates/              base.html + views + _macros.html (IEG branded)
static/                 brand.css + ieg-logo.png (shared IEG assets)
probe_list_connection.py         one-shot live-connection check
```

## Legacy

The original Streamlit build (`views/`, `components/ui.py`, `components/filters.py`,
`setup.py`, `.streamlit/`) and the CSV seed export were removed once the live Graph
connection became the source of truth. They remain in git history if ever needed:
`git log --diff-filter=D --oneline -- views/`. `utils/pacing.py`,
`components/financial_charts.py`, and `data/models.py` carried over into the Flask app.
