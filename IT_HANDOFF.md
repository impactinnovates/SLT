# SLT dashboard - IT handoff (two items to take it live)

A new internal app, **SLT Strategic Initiatives**, built the same way as
DemandPulse and the Financial Dashboard. Code is in
`github.com/impactinnovates/SLT` and ready. Two independent items are needed to
make it live; they can be worked in parallel.

---

## Item 1 - Stand up the Azure Web App (same pattern as demandpulse-ieg)

| Setting | Value |
|---|---|
| App name | `slt-ieg` |
| Plan | `asp-ieg-shared-b2` (Linux, shared) |
| Resource group | `rg-docrepo-prod-centus-001` |
| Runtime | Python 3.12 |
| Startup command | `gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app` |
| URL | `https://slt-ieg.azurewebsites.net` |

```bash
RG=rg-docrepo-prod-centus-001
az webapp create -g $RG -p asp-ieg-shared-b2 -n slt-ieg --runtime "PYTHON:3.12"
az webapp config set -g $RG -n slt-ieg --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app"
az webapp config appsettings set -g $RG -n slt-ieg --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true WEBSITES_CONTAINER_START_TIME_LIMIT=600
```

Passwordless deploy (OIDC), same as the other apps:

```bash
APPID=$(az ad app create --display-name "github-slt-ieg-deploy" --query appId -o tsv)
az ad sp create --id $APPID
az ad app federated-credential create --id $APPID --parameters '{
  "name":"slt-ieg-main",
  "issuer":"https://token.actions.githubusercontent.com",
  "subject":"repo:impactinnovates/SLT:ref:refs/heads/main",
  "audiences":["api://AzureADTokenExchange"]}'
SUB=$(az account show --query id -o tsv)
az role assignment create --assignee $APPID --role "Website Contributor" \
  --scope "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Web/sites/slt-ieg"
gh secret set AZURE_CLIENT_ID       -R impactinnovates/SLT -b "$APPID"
gh secret set AZURE_TENANT_ID       -R impactinnovates/SLT -b "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID -R impactinnovates/SLT -b "$SUB"
```

Sign-in (Entra SSO): add the redirect URI
`https://slt-ieg.azurewebsites.net/auth/callback` to the existing IEG sign-in app
registration, then set these app settings on `slt-ieg`:
`ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`,
`ENTRA_REDIRECT_URI=https://slt-ieg.azurewebsites.net/auth/callback`,
`SESSION_SECRET` (any long random string).

---

## Item 2 - Grant one app-only Graph permission (for the live List)

The app reads/writes one SharePoint List as a **service identity**
(`https://iegna.sharepoint.com/sites/2023IEGStrategicPlan`). On an Entra app
(reuse the DemandPulse app, or a new one):

1. Add **application permission** Microsoft Graph -> **`Sites.Selected`**
   (preferred) or **`Sites.ReadWrite.All`**, and **grant admin consent**.
2. If `Sites.Selected`: grant that app **write** on just this site (one Graph
   POST to `/sites/{id}/permissions`; details in `IT_REQUEST_graph_permission.md`).
3. Create a **client secret**.

---

## Please send back

- **Directory (tenant) ID**, **Application (client) ID**, **client secret value +
  expiry** (for the Graph app).
- Confirmation the `slt-ieg` deploy succeeded (or any error from the Actions run).

Full detail for both items lives in the repo: `AZURE_RUNBOOK.md` and
`IT_REQUEST_graph_permission.md`.
