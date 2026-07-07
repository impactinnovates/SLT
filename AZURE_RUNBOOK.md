# SLT Strategic Initiatives - Azure deployment runbook

How `slt-ieg` runs in Azure. This is a **Flask / WSGI** app, so it uses the same
setup as DemandPulse: Oryx builds it, gunicorn serves `wsgi:app`, and sign-in is
**in-app Microsoft Entra SSO** (auth.py) - NOT Easy Auth - because the app needs
the caller's identity to apply the SLT / PM / TM role layers.

| Item | Value |
|---|---|
| App Service name | `slt-ieg` |
| App Service Plan | `asp-ieg-shared-b2` (Basic B2, Linux) - shared with the other IEG apps |
| Resource group | `rg-docrepo-prod-centus-001` |
| Runtime | Python 3.12 |
| Public URL | `https://slt-ieg.azurewebsites.net` |
| Startup command | `gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app` |
| Auth | In-app Entra SSO (auth.py); enforced when `ENTRA_CLIENT_ID` is set |

---

## Data persistence (important)

Runtime edit overlays (`edits.json`, `sub_initiatives.json`) are written to
**`/home/site/data`** on Azure - the only location that survives restarts AND
redeploys. `config/settings.py` does this automatically when `WEBSITE_SITE_NAME`
is present (i.e. on App Service). The committed `Strategic_Initiatives_2026.csv`
stays in the code folder as read-only seed data.

Once the live List write-back is enabled (`LIST_WRITE_ENABLED=true`), edits go to
SharePoint and the local overlays are no longer the system of record - but keeping
them on `/home/site/data` means nothing is lost in the interim.

---

## 1. One-time provisioning

```bash
RG=rg-docrepo-prod-centus-001
PLAN=asp-ieg-shared-b2

az webapp create -g $RG -p $PLAN -n slt-ieg --runtime "PYTHON:3.12"

az webapp config set -g $RG -n slt-ieg \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app"

az webapp config appsettings set -g $RG -n slt-ieg --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  WEBSITES_CONTAINER_START_TIME_LIMIT=600
```

## 2. GitHub Actions OIDC (passwordless deploy)

`.github/workflows/main_slt-ieg.yml` deploys on push to `main` via OIDC - no
publish profile, no secrets in the repo.

```bash
APPID=$(az ad app create --display-name "github-slt-ieg-deploy" --query appId -o tsv)
az ad sp create --id $APPID

az ad app federated-credential create --id $APPID --parameters '{
  "name": "slt-ieg-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:impactinnovates/SLT:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

SUB=$(az account show --query id -o tsv)
az role assignment create --assignee $APPID --role "Website Contributor" \
  --scope "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Web/sites/slt-ieg"

gh secret set AZURE_CLIENT_ID       -R impactinnovates/SLT -b "$APPID"
gh secret set AZURE_TENANT_ID       -R impactinnovates/SLT -b "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID -R impactinnovates/SLT -b "$SUB"
```

## 3. Application settings (Entra SSO + live List)

Set these on the web app. SSO turns on only when `ENTRA_CLIENT_ID` is present;
the app fails fast at boot if it's half-configured.

```bash
az webapp config appsettings set -g $RG -n slt-ieg --settings \
  ENTRA_TENANT_ID="<tenant-id>" \
  ENTRA_CLIENT_ID="<sign-in-app-client-id>" \
  ENTRA_CLIENT_SECRET="<sign-in-app-secret>" \
  ENTRA_REDIRECT_URI="https://slt-ieg.azurewebsites.net/auth/callback" \
  SESSION_SECRET="<long-random-string>" \
  SHAREPOINT_SITE_URL="https://iegna.sharepoint.com/sites/2023IEGStrategicPlan" \
  LIST_NAME="<exact List display name from the probe>" \
  GRAPH_CLIENT_SECRET="<app-only Graph secret>" \
  LIST_WRITE_ENABLED="false"
```

- Add the redirect URI `https://slt-ieg.azurewebsites.net/auth/callback` to the
  Entra sign-in app registration (Authentication → Web → Redirect URIs).
- `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` default to the `ENTRA_*` values, so if the
  same app registration serves both sign-in and List access you only need
  `GRAPH_CLIENT_SECRET`. Otherwise set the `GRAPH_*` trio explicitly.
- Leave `LIST_WRITE_ENABLED=false` until the probe confirms the List's internal
  column names and `GRAPH_MAP` (data/models.py) is reconciled; then flip to `true`.

## 4. Roles

Access layers come from `config/roles.yaml` (committed), matched on the signed-in
identity. Editing a person's layer is a one-line change + a normal PR - no Azure
change needed.

---

## Smoke test after deploy

```bash
# Health probe is public.
curl -s -o /dev/null -w "%{http_code}\n" https://slt-ieg.azurewebsites.net/healthz   # 200

# Any page should 302 unauthenticated requests to Microsoft sign-in.
curl -s -o /dev/null -w "%{http_code}\n" https://slt-ieg.azurewebsites.net/dashboard  # 302
```

Then browse to the URL, sign in with a company account, and confirm you land on
the dashboard (SLT) / your initiatives (PM) / your tasks (TM) per your role.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `000` / ContainerTimeout | wrong startup command | set `gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app` |
| 500 at boot | SSO half-configured | app requires all `ENTRA_*` + `SESSION_SECRET` when `ENTRA_CLIENT_ID` is set |
| Sign-in loops / redirect error | redirect URI mismatch | Entra app redirect must equal `ENTRA_REDIRECT_URI` exactly |
| Edits vanish after a deploy | overlay on ephemeral disk | confirmed handled: overlays write to `/home/site/data` on Azure |
| Graph 403 on live List | app-only permission not consented | see `IT_REQUEST_graph_permission.md` |

Logs: `az webapp log tail -g rg-docrepo-prod-centus-001 -n slt-ieg`

---

## Branching workflow

Like the other IEG apps: **all changes go through a feature branch → PR → `main`**,
never a direct push to `main` (a merge to `main` auto-deploys `slt-ieg`). Recommend
enabling branch protection on `main` (require a PR) once the team is set up.
