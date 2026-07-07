"""
data/graph_client.py
App-only Microsoft Graph connector for the Strategic Initiatives SharePoint List.

Authenticates as a service identity (MSAL confidential app / client-credentials
flow) using the GRAPH_* settings, then reads and writes List items via Graph v1.0.
This is deliberately app-only: who-sees-what is enforced in the app by role, not
by each signed-in user's own SharePoint permissions.

Nothing here runs until settings.graph_is_configured() is True. The probe script
(probe_list_connection.py) exercises every method below without touching the app,
so we can confirm the connection is live before building on top of it.
"""
import logging
import requests
import msal

from config import settings

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES     = ["https://graph.microsoft.com/.default"]


class GraphError(RuntimeError):
    """Graph auth or a List call failed — carries a readable reason (no secrets)."""


class GraphClient:
    """Thin, app-only wrapper around Microsoft Graph for one SharePoint List."""

    def __init__(self):
        if not (settings.GRAPH_TENANT_ID and settings.GRAPH_CLIENT_ID
                and settings.GRAPH_CLIENT_SECRET):
            raise GraphError(
                "Graph app credentials are not configured "
                "(GRAPH_TENANT_ID / GRAPH_CLIENT_ID / GRAPH_CLIENT_SECRET)."
            )
        self._app = msal.ConfidentialClientApplication(
            settings.GRAPH_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}",
            client_credential=settings.GRAPH_CLIENT_SECRET,
        )
        self._site_id: str | None = None
        self._list_id: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────
    def _token(self) -> str:
        result = (self._app.acquire_token_silent(SCOPES, account=None)
                  or self._app.acquire_token_for_client(scopes=SCOPES))
        if "access_token" not in result:
            raise GraphError(
                f"Graph auth failed: {result.get('error')} - "
                f"{str(result.get('error_description', ''))[:300]}"
            )
        return result["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json"}

    def _get(self, url: str) -> dict:
        r = requests.get(url, headers=self._headers(), timeout=30)
        self._raise(r)
        return r.json()

    @staticmethod
    def _raise(r: requests.Response):
        if not r.ok:
            raise GraphError(f"Graph {r.request.method} {r.status_code}: {r.text[:400]}")

    # ── Site / list resolution (cached per client) ────────────────────────
    def site_id(self) -> str:
        if self._site_id:
            return self._site_id
        host, _, path = settings.SHAREPOINT_SITE_URL.replace("https://", "").partition("/")
        data = self._get(f"{GRAPH_BASE}/sites/{host}:/{path}")
        self._site_id = data["id"]
        return self._site_id

    def list_lists(self) -> list[dict]:
        """Every List on the site — used by the probe to confirm the exact
        display name to put in LIST_NAME."""
        data = self._get(f"{GRAPH_BASE}/sites/{self.site_id()}/lists"
                         "?$select=id,displayName,name,list")
        return [{
            "displayName": l.get("displayName"),
            "name":        l.get("name"),
            "id":          l.get("id"),
            "template":    (l.get("list") or {}).get("template"),
        } for l in data.get("value", [])]

    def list_id(self, list_name: str | None = None) -> str:
        name = list_name or settings.LIST_NAME
        if not name:
            raise GraphError("LIST_NAME is not set and no list name was provided.")
        if self._list_id and not list_name:
            return self._list_id
        for l in self.list_lists():
            if name in (l["displayName"], l["name"]):
                if not list_name:
                    self._list_id = l["id"]
                return l["id"]
        raise GraphError(f"List '{name}' not found on {settings.SHAREPOINT_SITE_URL}.")

    def list_columns(self, list_name: str | None = None) -> list[dict]:
        """Internal + display names of the List's columns. The internal names are
        what write-back must PATCH against — they differ from the SharePoint
        display names (e.g. '% Complete' -> 'PercentComplete' or '_x0025__Complete')."""
        lid = self.list_id(list_name)
        data = self._get(f"{GRAPH_BASE}/sites/{self.site_id()}/lists/{lid}/columns"
                         "?$select=name,displayName,readOnly,hidden")
        return [c for c in data.get("value", []) if not c.get("hidden")]

    # ── CRUD ──────────────────────────────────────────────────────────────
    def get_items(self, list_name: str | None = None) -> list[dict]:
        """All List items as flat field dicts. Each carries `_sp_item_id`
        (the SharePoint item id) for write-back."""
        lid = self.list_id(list_name)
        url = (f"{GRAPH_BASE}/sites/{self.site_id()}/lists/{lid}/items"
               "?expand=fields&$top=500")
        rows: list[dict] = []
        while url:
            data = self._get(url)
            for it in data.get("value", []):
                fields = dict(it.get("fields", {}))
                fields["_sp_item_id"] = it.get("id")
                rows.append(fields)
            url = data.get("@odata.nextLink")
        return rows

    def update_item(self, item_id: str, fields: dict, list_name: str | None = None) -> dict:
        lid = self.list_id(list_name)
        url = f"{GRAPH_BASE}/sites/{self.site_id()}/lists/{lid}/items/{item_id}/fields"
        r = requests.patch(url, headers=self._headers(), json=fields, timeout=30)
        self._raise(r)
        return r.json()

    def create_item(self, fields: dict, list_name: str | None = None) -> dict:
        lid = self.list_id(list_name)
        url = f"{GRAPH_BASE}/sites/{self.site_id()}/lists/{lid}/items"
        r = requests.post(url, headers=self._headers(), json={"fields": fields}, timeout=30)
        self._raise(r)
        return r.json().get("fields", {})

    def delete_item(self, item_id: str, list_name: str | None = None) -> None:
        """Delete a List item. The app must confirm sponsor permission first."""
        lid = self.list_id(list_name)
        url = f"{GRAPH_BASE}/sites/{self.site_id()}/lists/{lid}/items/{item_id}"
        r = requests.delete(url, headers=self._headers(), timeout=30)
        self._raise(r)


# Singleton — token + site/list ids are cached on the instance.
_client: GraphClient | None = None


def get_graph_client() -> GraphClient:
    global _client
    if _client is None:
        _client = GraphClient()
    return _client
