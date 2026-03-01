"""
fyers_mcp_auth.py  —  Fyers Login
==================================
Run once each morning before trading Indian stocks.

    py fyers_mcp_auth.py
"""

import os, sys, webbrowser
from urllib.parse import urlparse, parse_qs, urlencode
from dotenv import load_dotenv, set_key

ENV_PATH   = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

APP_ID       = os.getenv("FYERS_APP_ID")
SECRET_KEY   = os.getenv("FYERS_SECRET_KEY")
REDIRECT_URI = "https://www.google.com/"
STATE        = "sample_state"

try:
    import colorama; colorama.init(autoreset=True)
    G="\033[92m"; R="\033[91m"; C="\033[96m"; B="\033[1m"; X="\033[0m"
except ImportError:
    G=R=C=B=X=""

try:
    from fyers_apiv3 import fyersModel
except ImportError:
    print(R+"[ERROR] Run: py -m pip install fyers-apiv3"+X); sys.exit(1)

if not APP_ID or not SECRET_KEY:
    print(R+"[ERROR] FYERS_APP_ID and FYERS_SECRET_KEY missing in .env"+X); sys.exit(1)

# ── Build and open login URL ──────────────────────────
params  = {"client_id": APP_ID, "redirect_uri": REDIRECT_URI,
           "response_type": "code", "state": STATE}
auth_url = "https://api-t1.fyers.in/api/v3/generate-authcode?" + urlencode(params)

session = fyersModel.SessionModel(
    client_id=APP_ID, secret_key=SECRET_KEY,
    redirect_uri=REDIRECT_URI, response_type="code",
    grant_type="authorization_code", state=STATE
)

print(f"\n{B}{C}{'='*55}{X}")
print(f"  Fyers Login — App: {APP_ID}")
print(f"{B}{C}{'='*55}{X}\n")
print("  Opening browser... Log in with your Fyers account.\n")
webbrowser.open(auth_url)

print(f"  {C}After login, Google will open.{X}")
print("  The ADDRESS BAR will look like this:\n")
print(f"  {G}https://www.google.com/?auth_code=eyJ0eXAi...&state=sample_state{X}\n")
print("  Copy the FULL URL from the address bar and paste below.\n")

raw = input("  Paste URL here: ").strip()

# ── Parse auth_code ───────────────────────────────────
auth_code = None
if "auth_code=" in raw:
    try:
        auth_code = parse_qs(urlparse(raw).query).get("auth_code", [None])[0]
        if not auth_code:
            auth_code = raw.split("auth_code=")[1].split("&")[0]
    except Exception:
        pass
elif len(raw) > 30 and " " not in raw and "api.fyers" not in raw and "api-t1" not in raw:
    auth_code = raw  # raw token pasted directly

if not auth_code:
    print(f"\n{R}[ERROR] That doesn't look like a valid Google redirect URL.{X}")
    print(f"  You pasted: {raw[:100]}")
    print(f"\n  Expected: https://www.google.com/?auth_code=eyJ0...&state=sample_state")
    print(f"\n  Make sure you copied from Google's address bar AFTER logging in.")
    sys.exit(1)

print(f"\n  auth_code: {G}{auth_code[:20]}...{X}")

# ── Exchange for token ────────────────────────────────
print("  Getting access token from Fyers...")
session.set_token(auth_code)
resp = session.generate_token()

if resp.get("s") != "ok":
    msg = resp.get("message", str(resp))
    print(f"\n{R}[ERROR] {msg}{X}")
    print("  Auth codes expire in 60 seconds — run the script again and paste quickly.")
    sys.exit(1)

token = resp["access_token"]
set_key(ENV_PATH, "FYERS_ACCESS_TOKEN", token)

# ── Verify ────────────────────────────────────────────
try:
    fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, log_path="")
    prof  = fyers.get_profile()
    name  = prof.get("data", {}).get("name", "User") if prof.get("s") == "ok" else "User"
except Exception:
    name = "User"

print(f"\n{G}{B}{'='*55}")
print(f"  Logged in! Welcome, {name}")
print(f"{'='*55}{X}")
print(f"\n  Token saved.  Now run:  {C}py run_agent.py{X}\n")
