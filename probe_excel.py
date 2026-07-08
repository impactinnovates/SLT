"""
probe_excel.py
Read-only check that the app can reach a shared Excel file via Graph, and show
its worksheet layout so we can design the sync mapping.

    python probe_excel.py "<sharing-url>"

It resolves the SharePoint/OneDrive sharing link to a driveItem, then lists the
worksheets and previews the first rows of each. It NEVER writes anything.
"""
import sys
import base64
import requests

from config import settings

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GRAPH = "https://graph.microsoft.com/v1.0"


def encode_share_url(u: str) -> str:
    b = base64.b64encode(u.encode("utf-8")).decode("utf-8")
    return "u!" + b.rstrip("=").replace("/", "_").replace("+", "-")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python probe_excel.py \"<sharing-url>\"")
        return 2
    url = sys.argv[1]

    if not settings.graph_is_configured():
        print("Graph not configured (need GRAPH_* in .env).")
        return 1

    from data.graph_client import get_graph_client, GraphError
    client = get_graph_client()
    try:
        token = client._token()
    except GraphError as e:
        print(f"auth failed: {e}")
        return 1
    h = {"Authorization": f"Bearer {token}"}

    print("[1] Resolving the sharing link to a file ...")
    share_id = encode_share_url(url)
    r = requests.get(f"{GRAPH}/shares/{share_id}/driveItem"
                     "?$select=id,name,webUrl,parentReference,size", headers=h, timeout=30)
    if not r.ok:
        print(f"    ✗ {r.status_code}: {r.text[:300]}")
        if r.status_code in (403, 401):
            print("      The app identity cannot read this file. It's on personal")
            print("      OneDrive (iegna-my), which needs Files.Read.All (application)")
            print("      consent, OR the file must live on a SharePoint site the app")
            print("      can access, OR be shared directly with the app.")
        return 1
    item = r.json()
    drive_id = item["parentReference"]["driveId"]
    item_id = item["id"]
    print(f"    ✓ {item['name']}  ({item.get('size', '?')} bytes)")

    print("\n[2] Worksheets ...")
    r = requests.get(f"{GRAPH}/drives/{drive_id}/items/{item_id}/workbook/worksheets"
                     "?$select=name,position", headers=h, timeout=30)
    if not r.ok:
        print(f"    ✗ {r.status_code}: {r.text[:300]}")
        return 1
    sheets = r.json().get("value", [])
    print(f"    {len(sheets)} sheet(s): {[s['name'] for s in sheets]}")

    for s in sheets:
        name = s["name"]
        print(f"\n[3] Preview of '{name}' (first rows of used range) ...")
        rr = requests.get(
            f"{GRAPH}/drives/{drive_id}/items/{item_id}/workbook/worksheets/{name}/usedRange"
            "?$select=address,text", headers=h, timeout=45)
        if not rr.ok:
            print(f"    ✗ {rr.status_code}: {rr.text[:200]}")
            continue
        data = rr.json()
        text = data.get("text") or []
        print(f"    range: {data.get('address')}  ({len(text)} rows)")

        def col_letter(i):
            s, i = "", i + 1
            while i > 0:
                i, r = divmod(i - 1, 26)
                s = chr(65 + r) + s
            return s

        # Find the header row (the one containing "Strategic Initiative").
        hdr = next((n for n, row in enumerate(text)
                    if any("strategic initiative" in str(c).lower() for c in row)), 0)
        print(f"    header row = {hdr + 1}. Super-header rows above it:")
        for n in range(hdr):
            cells = [f"{col_letter(i)}={str(c)[:26]}" for i, c in enumerate(text[n]) if str(c).strip()]
            if cells:
                print(f"      row {n + 1}: " + " | ".join(cells))

        # Distinct Strategic Initiative values (column B, index 1) with row counts.
        from collections import Counter
        counts = Counter(str(r[1]).strip() for r in text[hdr + 1:]
                         if len(r) > 1 and str(r[1]).strip())
        print(f"\n    Distinct 'Strategic Initiative' values (col B), row counts:")
        for name, c in counts.most_common():
            print(f"      {c:>3}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
