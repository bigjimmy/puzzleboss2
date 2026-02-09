#!/usr/bin/env python3
"""
One-time migration script: pull personal emails from LDAP and set them as
recoveryEmail on corresponding Google Workspace accounts.

Usage:
    # Dry run (default) - shows what would be changed
    python3 scripts/backfill_recovery_emails.py

    # Actually apply changes
    python3 scripts/backfill_recovery_emails.py --apply

Requires:
    - python-ldap (pip install python-ldap)
    - Google Admin SDK credentials (admintoken.json)
    - LDAP config values in the config table (LDAP_HOST, LDAP_DOMAIN, etc.)
    - puzzleboss.yaml for DB connection

Run from the project root directory.
"""

import sys
import os
import json
import argparse

# Add parent directory to path so we can import pb libraries
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ldap
from pblib import configstruct, debug_log
import pbgooglelib
from googleapiclient.discovery import build
import googleapiclient.errors


def get_ldap_users():
    """Query LDAP for all users, return dict of {username: personal_email}."""
    host = configstruct.get("LDAP_HOST")
    domain = configstruct.get("LDAP_DOMAIN")

    if not host or not domain:
        print("ERROR: LDAP_HOST or LDAP_DOMAIN not set in config table.")
        sys.exit(1)

    print(f"Connecting to LDAP: ldap://{host}")
    print(f"Search base: {domain}")

    ldapconn = ldap.initialize("ldap://%s" % host)

    # Search for all users with an email attribute
    results = ldapconn.search_s(
        domain, ldap.SCOPE_SUBTREE, "(objectClass=inetOrgPerson)", ["uid", "email"]
    )

    users = {}
    for dn, entry in results:
        if not dn:
            continue
        uid_list = entry.get("uid", [])
        email_list = entry.get("email", [])
        if uid_list and email_list:
            username = uid_list[0].decode("utf-8").lower()
            email = email_list[0].decode("utf-8")
            users[username] = email

    ldapconn.unbind_s()
    print(f"Found {len(users)} users with email addresses in LDAP.\n")
    return users


def get_google_users(userservice, domain):
    """List all Google Workspace users, return dict of {username: current_recoveryEmail}."""
    users = {}
    page_token = None

    print(f"Listing Google Workspace users for domain: {domain}")

    while True:
        results = (
            userservice.users()
            .list(
                domain=domain,
                maxResults=500,
                pageToken=page_token,
                projection="full",
            )
            .execute()
        )

        for user in results.get("users", []):
            primary = user.get("primaryEmail", "")
            username = (primary.split("@")[0] if "@" in primary else primary).lower()
            recovery = user.get("recoveryEmail", "")
            users[username] = recovery

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    print(f"Found {len(users)} Google Workspace accounts.\n")
    return users


def update_recovery_email(userservice, username, domain, recovery_email):
    """Set recoveryEmail on a Google Workspace account. Returns (success, message)."""
    email = "%s@%s" % (username, domain)
    try:
        userservice.users().update(
            userKey=email, body={"recoveryEmail": recovery_email}
        ).execute()
        return True, "OK"
    except googleapiclient.errors.HttpError as e:
        msg = json.loads(e.content).get("error", {}).get("message", str(e))
        return False, msg


def main():
    parser = argparse.ArgumentParser(
        description="Backfill recovery emails from LDAP to Google Workspace"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply changes (default is dry run)",
    )
    args = parser.parse_args()

    if not args.apply:
        print("=" * 60)
        print("  DRY RUN MODE - no changes will be made")
        print("  Pass --apply to actually update Google accounts")
        print("=" * 60)
        print()

    # 1. Get all users from LDAP
    ldap_users = get_ldap_users()

    # 2. Get all Google Workspace users
    pbgooglelib.initadmin()
    domain = configstruct["DOMAINNAME"]
    userservice = build("admin", "directory_v1", credentials=pbgooglelib.admincreds)
    google_users = get_google_users(userservice, domain)

    # 3. Compare and update
    already_set = 0
    to_update = 0
    updated = 0
    errors = 0
    not_in_google = 0
    not_in_ldap = 0

    # Users in LDAP but not in Google
    for username in sorted(ldap_users.keys()):
        if username not in google_users:
            not_in_google += 1
            print(f"  SKIP  {username:20s}  (not found in Google Workspace)")
            continue

        ldap_email = ldap_users[username]
        current_recovery = google_users[username]

        if current_recovery == ldap_email:
            already_set += 1
            print(
                f"  OK    {username:20s}  recovery already set to {ldap_email}"
            )
            continue

        to_update += 1

        if current_recovery:
            action = f"CHANGE {current_recovery} -> {ldap_email}"
        else:
            action = f"SET    {ldap_email}"

        if args.apply:
            success, msg = update_recovery_email(
                userservice, username, domain, ldap_email
            )
            if success:
                updated += 1
                print(f"  DONE  {username:20s}  {action}")
            else:
                errors += 1
                print(f"  FAIL  {username:20s}  {action}  error: {msg}")
        else:
            print(f"  WOULD {username:20s}  {action}")

    # Report Google users not in LDAP
    for username in sorted(google_users.keys()):
        if username not in ldap_users:
            not_in_ldap += 1

    # Summary
    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  LDAP users:                   {len(ldap_users)}")
    print(f"  Google Workspace users:       {len(google_users)}")
    print(f"  Already have recovery email:  {already_set}")
    print(f"  Need recovery email set:      {to_update}")
    if args.apply:
        print(f"  Successfully updated:         {updated}")
        print(f"  Failed to update:             {errors}")
    print(f"  In LDAP but not Google:       {not_in_google}")
    print(f"  In Google but not LDAP:       {not_in_ldap}")
    print()

    if not args.apply and to_update > 0:
        print(f"Run with --apply to update {to_update} account(s).")


if __name__ == "__main__":
    main()
