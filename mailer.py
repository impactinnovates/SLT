"""
mailer.py
Outbound email via Microsoft Graph sendMail - the same mechanism the SCP and
other IEG dashboards use, so there's no SMTP server or mailbox password to manage.

It reuses the Entra app registration already configured for SSO (client-
credentials flow) and sends from MAIL_SENDER. To turn it on:
  - the app registration needs the Mail.Send *application* permission with admin
    consent (already granted for the other dashboards' shared app), and
  - set MAIL_SENDER to the from-address (a licensed or shared mailbox UPN).

send(to, subject, html) -> {"ok": bool, "message": str}. Never raises - a failed
send comes back as {"ok": False, ...} so a bad send is reported, not fatal.
"""
import re
import base64

from config import settings

_GRAPH = "https://graph.microsoft.com/v1.0"
_msal_app = None      # module-level so the token cache is reused across sends


def configured() -> bool:
    """True when everything Graph sendMail needs is present."""
    return bool(settings.MAIL_SENDER and settings.ENTRA_CLIENT_ID
                and settings.ENTRA_CLIENT_SECRET and settings.ENTRA_TENANT_ID)


def _recipients(to: str):
    return [{"emailAddress": {"address": a.strip()}}
            for a in re.split(r"[;,]", to or "") if a.strip()]


def _token() -> str:
    global _msal_app
    import msal
    if _msal_app is None:
        _msal_app = msal.ConfidentialClientApplication(
            settings.ENTRA_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}",
            client_credential=settings.ENTRA_CLIENT_SECRET)
    res = _msal_app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in res:
        raise RuntimeError("Graph token error: "
                           + str(res.get("error_description") or res.get("error")))
    return res["access_token"]


def send(to: str, subject: str, html: str, attachments=None) -> dict:
    """Send an HTML email. Returns {"ok", "message"}. See module docstring."""
    if not (to or "").strip():
        return {"ok": False, "message": "no recipient"}
    if not configured():
        return {"ok": False, "message":
                "email not enabled: set MAIL_SENDER (+ Mail.Send consent on the "
                "app registration) to send via Microsoft Graph"}
    try:
        import requests
        message = {
            "subject": subject or "(no subject)",
            "body": {"contentType": "HTML", "content": html or ""},
            "toRecipients": _recipients(to),
        }
        if attachments:
            message["attachments"] = [{
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name, "contentType": ctype or "application/octet-stream",
                "contentBytes": base64.b64encode(data).decode("ascii"),
            } for (name, data, ctype) in attachments]
        r = requests.post(
            f"{_GRAPH}/users/{settings.MAIL_SENDER}/sendMail",
            headers={"Authorization": "Bearer " + _token(),
                     "Content-Type": "application/json"},
            json={"message": message, "saveToSentItems": True}, timeout=30)
        if r.status_code not in (200, 202):
            return {"ok": False, "message": f"Graph sendMail HTTP {r.status_code}: {r.text[:200]}"}
        return {"ok": True, "message": f"sent via {settings.MAIL_SENDER}"}
    except Exception as exc:
        return {"ok": False, "message": f"send failed: {exc}"}
