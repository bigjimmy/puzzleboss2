#!/usr/bin/env python3
"""
Test whether we can use the service account (with Domain-Wide Delegation)
to obtain Google session cookies, eliminating the need for manual browser
cookie harvesting.

Run on production: python3 scripts/test_oauth_cookies.py

Approach 1: OAuthLogin — exchange OAuth2 token for session cookies (SID, etc.)
Approach 2: Bearer token — use OAuth2 token directly on /scripts/invoke
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import urllib.request
import urllib.error
import http.cookiejar
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from pblib import refresh_config, configstruct

refresh_config()

sa_file = configstruct.get("SERVICE_ACCOUNT_FILE", "service-account.json")
subject = configstruct.get("SERVICE_ACCOUNT_SUBJECT", "")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

print(f"Service account: {sa_file}")
print(f"Impersonating: {subject}")

creds = service_account.Credentials.from_service_account_file(
    sa_file, scopes=SCOPES, subject=subject
)
creds.refresh(Request())
token = creds.token
print(f"Access token: {token[:40]}...")

# ── Approach 1: OAuthLogin (token → uberauth → session cookies) ─────
print()
print("=" * 60)
print("Approach 1: OAuthLogin token-to-cookie exchange")
print("=" * 60)

try:
    oauth_url = (
        "https://accounts.google.com/accounts/OAuthLogin"
        "?source=puzzleboss&issueuberauth=1"
    )
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
    )
    req = urllib.request.Request(
        oauth_url, headers={"Authorization": f"Bearer {token}"}
    )
    response = opener.open(req, timeout=30)
    text = response.read().decode("utf-8", errors="replace")
    print(f"  Status: {response.status}")
    print(f"  Final URL: {response.url}")
    print(f"  Response body (first 300 chars): {text[:300]}")

    cookies_found = {}
    for cookie in cj:
        cookies_found[cookie.name] = cookie.value
        print(f"  Cookie: {cookie.name} = {str(cookie.value)[:50]}...")

    if "SID" in cookies_found:
        print()
        print("  ✅ SUCCESS: Got SID cookie! Full cookie exchange worked.")
        print("  Cookies obtained:", list(cookies_found.keys()))

        # If we got an uberauth token in the response, try MergeSession
        if "uberauth" in text.lower() or len(text.strip()) < 200:
            uberauth = text.strip()
            print(f"  Uberauth token: {uberauth[:50]}...")

            merge_url = (
                f"https://accounts.google.com/MergeSession"
                f"?uberauth={uberauth}"
                f"&continue=https://docs.google.com"
            )
            req2 = urllib.request.Request(merge_url)
            response2 = opener.open(req2, timeout=30)
            text2 = response2.read().decode("utf-8", errors="replace")
            print(f"  MergeSession status: {response2.status}")
            for cookie in cj:
                if cookie.name not in cookies_found:
                    print(f"  New cookie from MergeSession: {cookie.name}")
                    cookies_found[cookie.name] = cookie.value

    elif cookies_found:
        print(f"\n  ⚠️  Got cookies but no SID: {list(cookies_found.keys())}")
    else:
        print("\n  ❌ No cookies received from OAuthLogin")

except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace") if e.fp else ""
    print(f"  HTTP Error: {e.code} {e.reason}")
    print(f"  Body: {body[:300]}")
except Exception as e:
    print(f"  Error: {type(e).__name__}: {e}")

# ── Approach 2: Bearer token directly on /scripts/invoke ────────────
print()
print("=" * 60)
print("Approach 2: Bearer token on /scripts/invoke endpoint")
print("=" * 60)

invoke_params_json = configstruct.get("SHEETS_ADDON_INVOKE_PARAMS", "")
if not invoke_params_json:
    print("  SHEETS_ADDON_INVOKE_PARAMS not set, skipping")
else:
    invoke_params = json.loads(invoke_params_json)
    sid_param = invoke_params.get("sid", "")
    token_param = invoke_params.get("token", "")
    rest = invoke_params.get("_rest", "")

    # Find a real sheet to test against (query the API)
    try:
        import requests as req_lib

        api_uri = "http://localhost:5000"
        resp = req_lib.get(f"{api_uri}/all")
        data = resp.json()
        test_sheet = None
        for rnd in data.get("rounds", []):
            for puzzle in rnd.get("puzzles", []):
                did = puzzle.get("drive_id", "")
                if did and did != "xxxskippedbyconfigxxx" and puzzle.get("status") != "Solved":
                    test_sheet = {"id": puzzle["id"], "name": puzzle["name"], "drive_id": did}
                    break
            if test_sheet:
                break

        if not test_sheet:
            print("  No suitable puzzle sheet found for testing")
        else:
            print(f"  Testing against: {test_sheet['name']} ({test_sheet['drive_id'][:20]}...)")
            sheet_id = test_sheet["drive_id"]

            url = (
                f"https://docs.google.com/spreadsheets/u/0/d/{sheet_id}/scripts/invoke"
                f"?id={sheet_id}&sid={sid_param}&token={token_param}{rest}"
            )

            headers = {
                "Authorization": f"Bearer {token}",
                "x-same-domain": "1",
                "Content-Length": "0",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            }

            try:
                req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=30) as response:
                    resp_text = response.read().decode("utf-8", errors="replace")
                    resp_text = "\n".join(resp_text.split("\n")[1:]).strip()
                    print(f"  Status: {response.status}")
                    print(f"  Response: {resp_text[:200]}")
                    print(f"\n  ✅ SUCCESS: Bearer token accepted by /scripts/invoke!")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                print(f"  HTTP Error: {e.code} {e.reason}")
                print(f"  Body: {body[:300]}")
                if e.code == 401:
                    print("\n  ❌ Bearer token NOT accepted (401)")
                elif e.code == 403:
                    print("\n  ❌ Bearer token NOT authorized (403)")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("Done.")
print("=" * 60)
