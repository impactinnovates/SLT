"""
probe_list_connection.py
One-shot check that the app can reach the Strategic Initiatives Microsoft List.

Run it directly, from the SLT folder:

    python probe_list_connection.py

It does four things and prints the result of each, stopping at the first failure:

  1. Confirms the GRAPH_* settings are present.
  2. Acquires an app-only Graph token (proves the client id/secret + tenant work).
  3. Resolves the SharePoint site and lists every List on it — so you can confirm
     the exact display name to put in LIST_NAME.
  4. If LIST_NAME is set, reads back the List's columns (internal names) and one
     sample item. The internal names are what write-back needs.

No secrets are printed, and this NEVER modifies the List — read-only throughout.
"""
import sys

from config import settings

# Windows consoles default to cp1252, which can't encode item text or status
# glyphs. Force UTF-8 so the probe prints List data and markers reliably.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> int:
    print("SLT - Microsoft List connection probe")
    print("=" * 44)

    # ── 1. Configuration ──────────────────────────────────────────────────
    print("\n[1] Configuration")
    print(f"    Site URL : {settings.SHAREPOINT_SITE_URL or '(missing)'}")
    print(f"    List name: {settings.LIST_NAME or '(not set - will enumerate all)'}")
    print(f"    Tenant   : {'set' if settings.GRAPH_TENANT_ID else 'MISSING'}")
    print(f"    Client ID: {'set' if settings.GRAPH_CLIENT_ID else 'MISSING'}")
    print(f"    Secret   : {'set' if settings.GRAPH_CLIENT_SECRET else 'MISSING'}")

    if not settings.graph_is_configured():
        print("\n  ✗ Graph is not fully configured yet.")
        print("    Fill the GRAPH_* values in .env and make sure the app has")
        print("    admin-consented  Sites.ReadWrite.All  (or Sites.Selected on this")
        print("    site).  Then re-run this probe.  Stopping.")
        return 1

    # Imported here so the config-missing path above needs no msal install.
    from data.graph_client import get_graph_client, GraphError
    client = get_graph_client()

    # ── 2. Token ──────────────────────────────────────────────────────────
    print("\n[2] Acquiring app-only Graph token ...")
    try:
        client._token()
        print("    ✓ Token acquired.")
    except GraphError as e:
        print(f"    ✗ {e}")
        return 1

    # ── 3. Site + Lists ───────────────────────────────────────────────────
    print("\n[3] Resolving site and enumerating Lists ...")
    try:
        sid = client.site_id()
        print(f"    ✓ Site resolved (id ends …{sid[-12:]}).")
        lists = client.list_lists()
    except GraphError as e:
        print(f"    ✗ {e}")
        if "403" in str(e):
            print("      A 403 here usually means Sites.ReadWrite.All / Sites.Selected")
            print("      is not admin-consented for this app yet.")
        return 1

    print(f"    Found {len(lists)} List(s) on the site:")
    for l in lists:
        print(f"      - {l['displayName']!r}   (internal name: {l['name']})")

    # ── 4. Columns + sample item ──────────────────────────────────────────
    if not settings.LIST_NAME:
        print("\n  Next: copy the correct name above into LIST_NAME in .env, then")
        print("  re-run to read its columns and a sample item.")
        return 0

    print(f"\n[4] Reading columns + one sample item from {settings.LIST_NAME!r} ...")
    try:
        cols = client.list_columns()
        items = client.get_items()
    except GraphError as e:
        print(f"    ✗ {e}")
        return 1

    print("    Columns  (internal name -> display name):")
    for c in cols:
        ro = "  [read-only]" if c.get("readOnly") else ""
        print(f"      {c['name']:<30} {c.get('displayName', '')}{ro}")

    print(f"\n    Item count: {len(items)}")
    if items:
        print("    Sample item fields:")
        for k, v in list(items[0].items())[:24]:
            print(f"      {k:<30} {str(v)[:60]}")

    print("\n  ✓ Connection is live. The app can read this List.")
    print("    Reconcile these internal column names with GRAPH_MAP in")
    print("    data/models.py before turning the live read path on for users.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
