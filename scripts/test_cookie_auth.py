#!/usr/bin/env python3
"""
Test fresh cookies against the /scripts/invoke endpoint.
Diagnoses whether the issue is cookies, invoke params, or both.

Usage:
  # From raw Cookie header (paste the full Cookie: value):
  python3 scripts/test_cookie_auth.py --raw-cookies "COMPASS=...; SID=...; ..."

  # With invoke URL from DevTools (paste the full URL):
  python3 scripts/test_cookie_auth.py --raw-cookies "..." --invoke-url "https://docs.google.com/spreadsheets/u/0/d/SHEET_ID/scripts/invoke?id=...&sid=...&token=..."

  # From config DB (production):
  docker exec puzzleboss-app python3 /app/scripts/test_cookie_auth.py
"""
import sys
import os
import json
import urllib.request
import urllib.error
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_raw_cookies(raw):
    """Parse a raw Cookie header string into a dict."""
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name.strip()] = value.strip()
    return cookies


def parse_invoke_url(url):
    """Parse an invoke URL into the query_string format."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    full_query = parsed.query
    qs = parse_qs(full_query)

    return {
        "query_string": full_query,
        # Also extract individual params for display/validation
        "_sid": qs.get("sid", [""])[0],
        "_token": qs.get("token", [""])[0],
        "_lib": qs.get("lib", [""])[0],
        "_did": qs.get("did", [""])[0],
        "_ouid": qs.get("ouid", [""])[0],
    }


def main():
    parser = argparse.ArgumentParser(description="Test cookie auth for /scripts/invoke")
    parser.add_argument("--raw-cookies", help="Raw Cookie header value from browser")
    parser.add_argument("--invoke-url", help="Full invoke URL from browser DevTools")
    parser.add_argument("--sheet-id", help="Sheet ID to test against (overrides API lookup)")
    args = parser.parse_args()

    cookies = {}
    invoke_params = {}

    if args.raw_cookies:
        cookies = parse_raw_cookies(args.raw_cookies)
        print(f"Parsed {len(cookies)} cookies from raw header")
    else:
        # Load from config DB
        try:
            from pblib import refresh_config, configstruct
            refresh_config()
            cookies_json = configstruct.get("SHEETS_ADDON_COOKIES", "")
            invoke_params_json = configstruct.get("SHEETS_ADDON_INVOKE_PARAMS", "")
            if cookies_json:
                cookies = json.loads(cookies_json)
            if invoke_params_json:
                invoke_params = json.loads(invoke_params_json)
        except Exception as e:
            print(f"Could not load from config: {e}")
            sys.exit(1)

    if args.invoke_url:
        invoke_params = parse_invoke_url(args.invoke_url)
        print(f"Parsed invoke params from URL: sid={invoke_params['_sid'][:15]}... "
              f"token={invoke_params['_token'][:20]}...")

    if not cookies:
        print("ERROR: No cookies provided (use --raw-cookies or set SHEETS_ADDON_COOKIES)")
        sys.exit(1)

    print(f"\nCookies loaded ({len(cookies)}): {list(cookies.keys())}")
    if invoke_params:
        print(f"Invoke params keys: {list(invoke_params.keys())}")
    print()

    # Build cookie header
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

    # ── Test 1: Basic cookie auth ─────────────────────────────────
    print("=" * 60)
    print("Test 1: Basic cookie auth (fetch a Sheets page)")
    print("=" * 60)

    try:
        req = urllib.request.Request(
            "https://docs.google.com/spreadsheets/u/0/",
            headers={"Cookie": cookie_str}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            if "accounts.google.com/ServiceLogin" in text or "Sign in" in text:
                print("  ❌ Redirected to login — cookies are NOT valid")
            else:
                print(f"  ✅ Got Sheets homepage (status={resp.status}, {len(text)} bytes)")
                if "data-email" in text:
                    idx = text.index("data-email")
                    snippet = text[idx:idx + 100]
                    print(f"  Logged in as: {snippet}")
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP Error: {e.code} {e.reason}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # ── Test 2: /scripts/invoke ───────────────────────────────────
    print()
    print("=" * 60)
    print("Test 2: /scripts/invoke with full browser cookies + headers")
    print("=" * 60)

    # Get a test sheet ID
    test_sheet_id = args.sheet_id
    if not test_sheet_id:
        try:
            import requests as req_lib
            # Try config DB API URI, fall back to localhost
            try:
                from pblib import configstruct as cs
                api_uri = cs.get("API", {}).get("APIURI", "http://localhost:5000")
            except Exception:
                api_uri = "http://localhost:5000"
            resp = req_lib.get(f"{api_uri}/all", timeout=10)
            data = resp.json()
            for rnd in data.get("rounds", []):
                for puzzle in rnd.get("puzzles", []):
                    did = puzzle.get("drive_id", "")
                    if did and did != "xxxskippedbyconfigxxx":
                        test_sheet_id = did
                        print(f"  Using sheet: {puzzle['name']} ({did[:20]}...)")
                        break
                if test_sheet_id:
                    break
        except Exception as e:
            print(f"  Could not reach API: {e}")

    if not test_sheet_id:
        print("  No test sheet found. Use --sheet-id or ensure API is running.")
        sys.exit(0)

    # Build URL from invoke_params (supports both query_string and legacy format)
    import re
    if "query_string" in invoke_params:
        qs = invoke_params["query_string"]
        # Replace id= params with target sheet
        qs = qs.lstrip("?")
        qs = re.sub(r'(^|(?<=&))id=[^&]*', f'id={test_sheet_id}', qs)
        url = f"https://docs.google.com/spreadsheets/u/0/d/{test_sheet_id}/scripts/invoke?{qs}"
        # Extract display values from query string
        from urllib.parse import parse_qs
        qs_parsed = parse_qs(qs)
        sid = qs_parsed.get("sid", [""])[0]
        token = qs_parsed.get("token", [""])[0]
    else:
        # Legacy format
        sid = invoke_params.get("sid", "")
        token = invoke_params.get("token", "")
        lib = invoke_params.get("lib", "")
        did = invoke_params.get("did", "")
        ouid = invoke_params.get("ouid", "")

        if not sid or not token:
            print("  No invoke params (sid/token). Use --invoke-url or set SHEETS_ADDON_INVOKE_PARAMS")
            sys.exit(0)

        if not lib or not did:
            print("  WARNING: Missing lib/did params — invoke will likely fail (400)")

        from urllib.parse import quote
        token_encoded = quote(token, safe="")
        url = (
            f"https://docs.google.com/spreadsheets/u/0/d/{test_sheet_id}/scripts/invoke"
            f"?id={test_sheet_id}&sid={sid}&token={token_encoded}"
            f"&lib={lib}&did={did}&func=populateMenus"
        )
        if ouid:
            url += f"&ouid={ouid}"

    print(f"  URL: ...invoke?id=...&sid={sid[:10]}...&token={token[:20]}...")

    # Full browser-like headers (matching what puzzcord sends)
    headers = {
        "Cookie": cookie_str,
        "x-same-domain": "1",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": "https://docs.google.com",
        "Referer": f"https://docs.google.com/spreadsheets/d/{test_sheet_id}/edit",
        "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

    try:
        req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            text_clean = "\n".join(text.split("\n")[1:]).strip()
            print(f"  ✅ Status: {resp.status}")
            print(f"  Response: {text_clean[:300]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"  ❌ HTTP Error: {e.code} {e.reason}")
        print("  Response headers:")
        for h in ["WWW-Authenticate", "X-Frame-Options", "Content-Type", "Location"]:
            val = e.headers.get(h)
            if val:
                print(f"    {h}: {val}")
        print(f"  Body (first 500 chars): {body[:500]}")

        if e.code == 401:
            print()
            print("  Diagnosis: 401 means either:")
            print("  a) Cookies are invalid/expired (check Test 1 result)")
            print("  b) Invoke params (sid/token) are session-tied and need refreshing")
            print("  c) Missing required cookies")
            print()
            print(f"  Current cookie names ({len(cookies)}): {sorted(cookies.keys())}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

    # ── Test 3: Minimal cookie test (find which cookies are actually needed) ──
    print()
    print("=" * 60)
    print("Test 3: Cookie subset tests (identifying minimum required set)")
    print("=" * 60)

    # Test with progressively larger cookie subsets
    cookie_groups = [
        ("Core 4 (puzzcord original)", ["SID", "OSID", "__Secure-1PSID", "__Secure-1PSIDTS"]),
        ("Core + SIDCC family", ["SID", "OSID", "__Secure-1PSID", "__Secure-1PSIDTS",
                                  "SIDCC", "__Secure-1PSIDCC", "__Secure-3PSIDCC"]),
        ("Core + SAPISI* family", ["SID", "OSID", "__Secure-1PSID", "__Secure-1PSIDTS",
                                    "HSID", "SSID", "APISID", "SAPISID",
                                    "__Secure-1PAPISID", "__Secure-3PAPISID"]),
        ("All session cookies (no tracking)", [
            "SID", "OSID", "__Secure-OSID",
            "__Secure-1PSID", "__Secure-3PSID",
            "__Secure-1PSIDTS", "__Secure-3PSIDTS",
            "HSID", "SSID", "APISID", "SAPISID",
            "__Secure-1PAPISID", "__Secure-3PAPISID",
            "SIDCC", "__Secure-1PSIDCC", "__Secure-3PSIDCC",
        ]),
    ]

    for group_name, cookie_names in cookie_groups:
        subset = {k: v for k, v in cookies.items() if k in cookie_names}
        missing = [k for k in cookie_names if k not in cookies]
        present = len(subset)

        if present == 0:
            print(f"\n  {group_name}: SKIP (0 cookies available)")
            continue

        subset_str = "; ".join(f"{k}={v}" for k, v in subset.items())
        test_headers = dict(headers)
        test_headers["Cookie"] = subset_str

        try:
            req = urllib.request.Request(url, data=b"", headers=test_headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                text_clean = "\n".join(text.split("\n")[1:]).strip()
                print(f"\n  {group_name} ({present} cookies): ✅ {resp.status}")
                print(f"  Response: {text_clean[:100]}")
                break  # Found working set, no need to test more
        except urllib.error.HTTPError as e:
            _ = e.read() if e.fp else None  # drain response
            print(f"\n  {group_name} ({present} cookies): ❌ {e.code}")
            if missing:
                print(f"  (missing from input: {missing})")
        except Exception as e:
            print(f"\n  {group_name}: ❌ {e}")


if __name__ == "__main__":
    main()
