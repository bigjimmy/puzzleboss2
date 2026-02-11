#!/usr/bin/env python3
"""
Build SHEETS_ADDON_COOKIES and SHEETS_ADDON_INVOKE_PARAMS JSON config values
from raw browser data (Cookie header + invoke URL from DevTools).

Usage:
  python3 scripts/build_addon_config.py \
    --raw-cookies "COMPASS=...; SID=...; ..." \
    --invoke-url "https://docs.google.com/.../scripts/invoke?id=...&sid=...&token=..."

Output: JSON strings ready to paste into the puzzleboss config table.
"""
import sys
import json
import argparse
from urllib.parse import urlparse, parse_qs


def parse_raw_cookies(raw):
    """Parse a raw Cookie header string into a dict."""
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, value = part.split("=", 1)
            cookies[name.strip()] = value.strip()
    return cookies


def main():
    parser = argparse.ArgumentParser(
        description="Build SHEETS_ADDON_COOKIES and SHEETS_ADDON_INVOKE_PARAMS config JSON"
    )
    parser.add_argument("--raw-cookies", required=True,
                        help="Raw Cookie header value from browser DevTools")
    parser.add_argument("--invoke-url", required=True,
                        help="Full invoke URL from browser DevTools Network tab")
    args = parser.parse_args()

    # Parse cookies
    cookies = parse_raw_cookies(args.raw_cookies)
    print(f"Parsed {len(cookies)} cookies:")
    for name in sorted(cookies.keys()):
        val = cookies[name]
        print(f"  {name} = {val[:30]}{'...' if len(val) > 30 else ''}")

    # Parse invoke URL — store full query string to preserve all browser params
    parsed = urlparse(args.invoke_url)
    full_query = parsed.query
    qs = parse_qs(full_query)

    sid = qs.get("sid", [""])[0]
    token = qs.get("token", [""])[0]
    lib = qs.get("lib", [""])[0]
    did = qs.get("did", [""])[0]
    ouid = qs.get("ouid", [""])[0]

    if not lib or not did:
        print("\n⚠️  WARNING: invoke URL missing 'lib' or 'did' params.")
        print("  Make sure you captured a /scripts/invoke URL (not a regular sheet URL).")

    invoke_params = {"query_string": full_query}

    print(f"\nInvoke params (full query string preserved):")
    print(f"  sid   = {sid[:20]}{'...' if len(sid) > 20 else ''}")
    print(f"  token = {token[:30]}{'...' if len(token) > 30 else ''}")
    print(f"  lib   = {lib[:30]}{'...' if len(lib) > 30 else ''}")
    print(f"  did   = {did[:30]}{'...' if len(did) > 30 else ''}")
    print(f"  ouid  = {ouid or '(empty)'}")
    print(f"  total query params: {len(qs)}")

    # Output JSON config values
    cookies_json = json.dumps(cookies)
    invoke_json = json.dumps(invoke_params)

    print("\n" + "=" * 60)
    print("SHEETS_ADDON_COOKIES value:")
    print("=" * 60)
    print(cookies_json)

    print("\n" + "=" * 60)
    print("SHEETS_ADDON_INVOKE_PARAMS value:")
    print("=" * 60)
    print(invoke_json)

    print("\n" + "=" * 60)
    print("SQL to update config (if you prefer):")
    print("=" * 60)
    # Escape single quotes for SQL
    cookies_sql = cookies_json.replace("'", "''")
    invoke_sql = invoke_json.replace("'", "''")
    print(f"UPDATE config SET cfgval = '{cookies_sql}' WHERE cfgkey = 'SHEETS_ADDON_COOKIES';")
    print(f"UPDATE config SET cfgval = '{invoke_sql}' WHERE cfgkey = 'SHEETS_ADDON_INVOKE_PARAMS';")


if __name__ == "__main__":
    main()
