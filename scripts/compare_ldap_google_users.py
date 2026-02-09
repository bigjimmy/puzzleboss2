#!/usr/bin/env python3
"""
Compare LDAP and Google Workspace users to find unmatched accounts
and suggest possible links between them.

Usage:
    python3 scripts/compare_ldap_google_users.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ldap
from pblib import configstruct
import pbgooglelib
from googleapiclient.discovery import build


def get_ldap_users():
    """Get all LDAP users with full details."""
    host = configstruct.get("LDAP_HOST")
    domain = configstruct.get("LDAP_DOMAIN")

    ldapconn = ldap.initialize("ldap://%s" % host)
    results = ldapconn.search_s(
        domain,
        ldap.SCOPE_SUBTREE,
        "(objectClass=inetOrgPerson)",
        ["uid", "email", "mail", "givenName", "sn", "cn", "displayName"],
    )

    users = {}
    for dn, entry in results:
        if not dn:
            continue
        uid = entry.get("uid", [b""])[0].decode("utf-8")
        if not uid:
            continue
        users[uid] = {
            "uid": uid,
            "email": entry.get("email", [b""])[0].decode("utf-8"),
            "mail": entry.get("mail", [b""])[0].decode("utf-8"),
            "givenName": entry.get("givenName", [b""])[0].decode("utf-8"),
            "sn": entry.get("sn", [b""])[0].decode("utf-8"),
            "cn": entry.get("cn", [b""])[0].decode("utf-8"),
            "displayName": entry.get("displayName", [b""])[0].decode("utf-8"),
        }

    ldapconn.unbind_s()
    return users


def get_google_users(userservice, domain):
    """Get all Google Workspace users with full details."""
    users = {}
    page_token = None

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
            username = primary.split("@")[0] if "@" in primary else primary
            name = user.get("name", {})
            users[username] = {
                "username": username,
                "primaryEmail": primary,
                "givenName": name.get("givenName", ""),
                "familyName": name.get("familyName", ""),
                "fullName": name.get("fullName", ""),
                "recoveryEmail": user.get("recoveryEmail", ""),
                "suspended": user.get("suspended", False),
                "creationTime": user.get("creationTime", ""),
                "lastLoginTime": user.get("lastLoginTime", ""),
            }

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return users


def find_possible_matches(ldap_orphans, google_orphans):
    """Try to match orphaned LDAP users to orphaned Google users."""
    matches = []

    for l_uid, l_info in ldap_orphans.items():
        l_email = l_info["email"].lower()
        l_given = l_info["givenName"].lower()
        l_sn = l_info["sn"].lower()
        l_cn = l_info["cn"].lower()
        l_uid_lower = l_uid.lower()

        for g_uid, g_info in google_orphans.items():
            g_recovery = g_info["recoveryEmail"].lower()
            g_given = g_info["givenName"].lower()
            g_family = g_info["familyName"].lower()
            g_full = g_info["fullName"].lower()
            g_uid_lower = g_uid.lower()

            reasons = []

            # Check email match
            if l_email and g_recovery and l_email == g_recovery:
                reasons.append("recovery email matches LDAP email")

            # Check if LDAP uid is contained in Google username or vice versa
            if l_uid_lower in g_uid_lower or g_uid_lower in l_uid_lower:
                reasons.append("username substring match")

            # Check name matches
            if l_given and g_given and l_given == g_given:
                reasons.append("first name matches")
            if l_sn and g_family and l_sn == g_family:
                reasons.append("last name matches")
            if l_cn and g_full and l_cn == g_full:
                reasons.append("full name matches")

            # Check if LDAP email prefix matches Google username
            if l_email and "@" in l_email:
                l_email_prefix = l_email.split("@")[0].lower()
                if l_email_prefix == g_uid_lower:
                    reasons.append("LDAP email prefix matches Google username")
                if g_uid_lower in l_email_prefix or l_email_prefix in g_uid_lower:
                    reasons.append("LDAP email prefix ~ Google username")

            # Check name components in usernames
            if l_given and l_sn:
                # e.g. LDAP uid=tierneyj, Google uid=jtierney
                if l_sn in g_uid_lower and l_given[0] in g_uid_lower:
                    reasons.append("name components in Google username")
                if l_given in g_uid_lower or l_sn in g_uid_lower:
                    reasons.append("LDAP name component in Google username")
            if g_given and g_family:
                if g_family in l_uid_lower or g_given in l_uid_lower:
                    reasons.append("Google name component in LDAP username")

            if reasons:
                matches.append((l_uid, g_uid, reasons))

    return matches


def main():
    # Get all users from both sources
    print("Loading LDAP users...")
    ldap_users = get_ldap_users()
    print(f"  Found {len(ldap_users)} LDAP users\n")

    print("Loading Google Workspace users...")
    pbgooglelib.initadmin()
    domain = configstruct["DOMAINNAME"]
    userservice = build("admin", "directory_v1", credentials=pbgooglelib.admincreds)
    google_users = get_google_users(userservice, domain)
    print(f"  Found {len(google_users)} Google users\n")

    # Find orphans
    ldap_only = {k: v for k, v in ldap_users.items() if k not in google_users}
    google_only = {k: v for k, v in google_users.items() if k not in ldap_users}

    # Display LDAP-only users
    print("=" * 80)
    print("  USERS IN LDAP BUT NOT GOOGLE (%d)" % len(ldap_only))
    print("=" * 80)
    for uid in sorted(ldap_only.keys(), key=str.lower):
        info = ldap_only[uid]
        print(f"  {uid:25s}  name: {info['cn']:30s}  email: {info['email']}")
    print()

    # Display Google-only users
    print("=" * 80)
    print("  USERS IN GOOGLE BUT NOT LDAP (%d)" % len(google_only))
    print("=" * 80)
    for uid in sorted(google_only.keys(), key=str.lower):
        info = google_only[uid]
        suspended = " [SUSPENDED]" if info["suspended"] else ""
        print(
            f"  {uid:25s}  name: {info['fullName']:30s}  recovery: {info['recoveryEmail']}{suspended}"
        )
        print(
            f"  {'':25s}  created: {info['creationTime'][:10]}  last login: {info['lastLoginTime'][:10] if info['lastLoginTime'] else 'never'}"
        )
    print()

    # Find and display possible matches
    matches = find_possible_matches(ldap_only, google_only)

    print("=" * 80)
    print("  POSSIBLE MATCHES (%d)" % len(matches))
    print("=" * 80)
    if matches:
        for l_uid, g_uid, reasons in matches:
            l_info = ldap_only[l_uid]
            g_info = google_only[g_uid]
            print(f"\n  LDAP: {l_uid:20s}  ({l_info['cn']}, {l_info['email']})")
            print(
                f"  GOOG: {g_uid:20s}  ({g_info['fullName']}, {g_info['recoveryEmail']})"
            )
            print(f"  WHY:  {', '.join(reasons)}")
    else:
        print("  No possible matches found.")
    print()


if __name__ == "__main__":
    main()
