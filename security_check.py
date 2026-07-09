"""
security_check.py  -  role/access regression test.  Run: python security_check.py

Verifies the properties that matter for SLT initiatives being confidential:
  1. Leaders and Members get 403 on every SLT route (initiatives, financials,
     board, performance, sync, admin, ...). They can never load initiative data.
  2. Non-SLT roles cannot hit the write endpoints.
  3. The Admin screen is gated by ADMIN_EMAILS only (env-controlled, fail-closed).

Exits non-zero if any check fails, so it can run in CI / before a deploy.
"""
import sys

from app import app

SLT_ROUTES = ["/dashboard", "/initiatives", "/financial", "/performance",
              "/timeline", "/board", "/new", "/sync"]

fails = []
c = app.test_client()


def check(desc, ok):
    print(("PASS" if ok else "FAIL"), "-", desc)
    if not ok:
        fails.append(desc)


# 1. Leaders/Members blocked from every SLT route (data never rendered).
for role in ("Leader", "Member"):
    for r in SLT_ROUTES:
        code = c.get(f"{r}?as={role}").status_code
        check(f"{role} blocked from {r} (403, got {code})", code == 403)

# 2. Write endpoints refuse non-SLT.
check("Member cannot create an initiative",
      c.post("/api/initiative?as=Member", data={"name": "x"}).status_code == 403)
check("Member cannot add a task",
      c.post("/api/initiative/1/task?as=Member", data={"name": "x"}).status_code == 403)
check("Leader cannot add a task under an initiative",
      c.post("/api/initiative/1/task?as=Leader", data={"name": "x"}).status_code == 403)

# 3. Admin gate is env-controlled and fail-closed (simulate production SSO).
import auth
from config import settings
_saved = (settings.ADMIN_EMAILS, auth.AUTH_ENABLED)
try:
    auth.AUTH_ENABLED = True
    settings.ADMIN_EMAILS = {"admin@iegna.com"}
    check("listed admin IS admin", auth.is_admin({"email": "admin@iegna.com", "role": "SLT"}))
    check("unlisted SLT is NOT admin", not auth.is_admin({"email": "slt@iegna.com", "role": "SLT"}))
    check("leader is NOT admin", not auth.is_admin({"email": "l@iegna.com", "role": "Leader"}))
    settings.ADMIN_EMAILS = set()
    check("empty ADMIN_EMAILS -> nobody is admin (fail closed)",
          not auth.is_admin({"email": "admin@iegna.com", "role": "SLT"}))
finally:
    settings.ADMIN_EMAILS, auth.AUTH_ENABLED = _saved

if fails:
    print(f"\n{len(fails)} SECURITY CHECK(S) FAILED")
    sys.exit(1)
print("\nAll security checks passed.")
sys.exit(0)
