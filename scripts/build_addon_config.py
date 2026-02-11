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

    # Parse invoke URL
    parsed = urlparse(args.invoke_url)
    qs = parse_qs(parsed.query)

    sid = qs.get("sid", [""])[0]
    token = qs.get("token", [""])[0]

    # Reconstruct _rest from remaining params (excluding id, sid, token)
    rest_parts = []
    for key, values in qs.items():
        if key not in ("id", "sid", "token"):
            for v in values:
                rest_parts.append(f"&{key}={v}")
    _rest = "".join(rest_parts)

    invoke_params = {"sid": sid, "token": token, "_rest": _rest}

    print(f"\nInvoke params:")
    print(f"  sid = {sid[:20]}...")
    print(f"  token = {token[:30]}...")
    print(f"  _rest = {_rest[:60]}...")

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
