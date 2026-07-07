# IT Request: app-only Graph permission for the Strategic Initiatives dashboard

**Ask:** an internal dashboard needs to read and write items in one SharePoint List
using an **app-only (application) identity** - not each user's own permissions.
Users sign into the dashboard with their Microsoft account (already working); the
app reads/writes the List as a service identity, and the dashboard enforces
who-sees-what internally by role.

## The List / site
`https://iegna.sharepoint.com/sites/2023IEGStrategicPlan`

## The app registration
Either **reuse the existing DemandPulse Entra app** (fastest - just add the
permission + a secret below), or **create a new app** named `IEG Strategic Initiatives`.

## Please do three things
1. **Add an application permission** on that app: Microsoft Graph -> **Application
   permissions** ->
   - **`Sites.Selected`** (preferred - least privilege), or
   - **`Sites.ReadWrite.All`** (simpler, but tenant-wide).
2. **Grant admin consent** for that permission.
3. **Create a client secret** and send its **value + expiry**.

## If you choose `Sites.Selected` (recommended)
It needs one per-site write grant so the app can touch only this site:
```
# 1. Get the site id
GET https://graph.microsoft.com/v1.0/sites/iegna.sharepoint.com:/sites/2023IEGStrategicPlan

# 2. Grant this app write access to only that site
POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
{
  "roles": ["write"],
  "grantedToIdentities": [
    { "application": { "id": "{application-client-id}",
                       "displayName": "IEG Strategic Initiatives" } }
  ]
}
```
With `Sites.ReadWrite.All` instead, skip this step - consent alone is enough.

## Please send back
- **Directory (tenant) ID**
- **Application (client) ID**
- **Client secret value + expiry**

## Tradeoff, briefly
- `Sites.Selected` = app can touch only this one site. Cleanest; costs one extra grant.
- `Sites.ReadWrite.All` = one consent click, but the app could reach every site in
  the tenant. Broader than needed, but supported by the code as-is.

Either option works with the dashboard unchanged.
