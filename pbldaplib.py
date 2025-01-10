import ldap
import json
import requests
import pblib
import pbgooglelib
from pblib import *
from pbgooglelib import *
from ldap import modlist


def verify_email_for_user(email, username):
    debug_log(4, "start, called with (email, username): %s, %s" % (email, username))

    ldapconn = ldap.initialize("ldap://%s" % configstruct["LDAP_HOST"])

    result = ldapconn.search_s(
        configstruct["LDAP_DOMAIN"], ldap.SCOPE_SUBTREE, "email=%s" % email, ["uid"]
    )
    debug_log(4, "result of ldap search for %s is %s" % (email, result))

    match = 0
    for dn, entry in result:
        if entry["uid"][0].decode("utf8").lower() == username.lower():
            match = 1

    ldapconn.unbind_s()
    return match


def delete_user(username):
    debug_log(4, "start, called with username %s" % username)

    ldapconn = ldap.initialize("ldap://%s" % configstruct["LDAP_HOST"])
    ldapconn.simple_bind_s(configstruct["LDAP_ADMINDN"], configstruct["LDAP_ADMINPW"])

    debug_log(4, "admin bound to ldap with dn: %s" % configstruct["LDAP_ADMINDN"])
    userdn = "uid=%s,%s" % (username, configstruct["LDAP_DOMAIN"])

    errmsg = ""

    # delete user from ldap

    try:
        ldapconn.delete_s(userdn)
        debug_log(3, "user %s deleted from LDAP" % username)
    except Exception as e:
        errmsg = "LDAP:" + str(e)
        debug_log(
            2,
            "Exception deleting user %s from LDAP (already gone?): %s"
            % (username, errmsg),
        )

    # delete from google

    try:
        delete_google_user(username)
        debug_log(3, "user %s deleted from google domain" % username)
    except Exception as e:
        errmsg = errmsg + " GOOGLE:" + str(e)
        debug_log(
            2,
            "Exception deleting user %s from google (already gone?): %s"
            % (username, errmsg),
        )

    if errmsg == "":
        return "OK"

    return errmsg


def add_or_update_user(username, firstname, lastname, email, password):
    debug_log(
        4,
        "start, called with (username, firstname, lastname, email, password): %s %s %s %s REDACTED"
        % (username, firstname, lastname, email),
    )

    if verify_email_for_user(email, username) == 1:
        operation = "update"
    else:
        operation = "new"

    debug_log(4, "based on user existence, operation requested is: %s" % operation)

    ldapconn = ldap.initialize("ldap://%s" % configstruct["LDAP_HOST"])
    ldapconn.simple_bind_s(configstruct["LDAP_ADMINDN"], configstruct["LDAP_ADMINPW"])

    debug_log(4, "admin bound to ldap with dn: %s" % configstruct["LDAP_ADMINDN"])

    userdn = "uid=%s,%s" % (username, configstruct["LDAP_DOMAIN"])

    fullname = "%s %s" % (firstname, lastname)
    mailaddr = "%s@%s" % (username, configstruct["DOMAINNAME"])

    if operation == "new":
        newuserattrs = {}
        newuserattrs["objectclass"] = ["inetOrgPerson".encode("utf-8")]
        newuserattrs["uid"] = username.encode("utf-8")
        newuserattrs["sn"] = lastname.encode("utf-8")
        newuserattrs["givenName"] = firstname.encode("utf-8")
        newuserattrs["cn"] = fullname.encode("utf-8")
        newuserattrs["displayName"] = fullname.encode("utf-8")
        newuserattrs["userPassword"] = password.encode("utf-8")
        newuserattrs["email"] = email.encode("utf-8")
        newuserattrs["mail"] = mailaddr.encode("utf-8")
        newuserattrs["o"] = configstruct["LDAP_LDAPO"].encode("utf-8")

        # Add to google
        googaddresponse = add_user_to_google(username, firstname, lastname, password)
        debug_log(
            3,
            "Attempt to add %s to google domain. Response: %s"
            % (username, googaddresponse),
        )

        if googaddresponse != "OK":
            errmsg = "Failure in adding user to google: %s" % googaddresponse
            debug_log(0, errmsg)
            return errmsg

        # Add to LDAP
        ldif = ldap.modlist.addModlist(newuserattrs)
        ldapconn.add_s(userdn, ldif)
        debug_log(3, "Added %s to ldap" % username)

        # Add to solver DB
        postbody = {"fullname": "%s %s" % (firstname, lastname), "name": username}
        solveraddresponse = requests.post(
            "%s/solvers" % config["API"]["APIURI"], json=postbody
        )
        debug_log(
            4,
            "Attempt to add %s to solvers db. Response: %s"
            % (username, solveraddresponse.text),
        )

        if not solveraddresponse.ok:
            errmsg = "Failure adding user to solver DB. Contact admin."
            debug_log(0, errmsg)
            return errmsg

    if operation == "update":
        debug_log(3, "Updating password (google and LDAP) for user %s" % username)

        # Change password at google
        googchangeresponse = change_google_user_password(username, password)

        if googchangeresponse != "OK":
            errmsg = (
                "Failure in changing password at google for user: %s"
                % googchangeresponse
            )
            debug_log(0, errmsg)
            return errmsg

        # Change password in ldap
        ldapconn.modify_s(
            userdn, [(ldap.MOD_REPLACE, "userPassword", password.encode("utf-8"))]
        )

    ldapconn.unbind_s()
    return "OK"
