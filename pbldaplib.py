import ldap
from ldap import modlist
import json
import requests
import pblib
from pblib import *

def verify_email_for_user(email, username):
    debug_log(4, "start, called with (email, username): %s, %s" % (email, username))
        
    ldapconn = ldap.initialize('ldap://%s' % config['LDAP']['HOST'])
        
    result = ldapconn.search_s(config['LDAP']['DOMAIN'],
                               ldap.SCOPE_SUBTREE,
                               'email=%s' % email,
                               ['uid'])
    debug_log(4, "result of ldap search for %s is %s" % (email, result))
    
    match = 0
    for dn,entry in result:
        if entry['uid'][0].decode('utf8').lower() == username.lower():
            match = 1
    
    ldapconn.unbind_s()
    return(match)

def add_or_update_user(username, firstname, lastname, email, password):
    debug_log(4, "start, called with (username, firstname, lastname, email, password): %s %s %s %s REDACTED" % 
              (username, firstname, lastname, email))
    
    if verify_email_for_user(email, username) == 1:
        operation = "update"
    else:
        operation = "new"
        
    debug_log(4, "based on user existence, operation requested is: %s" % operation)
    
    ldapconn = ldap.initialize('ldap://%s' % config['LDAP']['HOST'])
    ldapconn.simple_bind_s(config['LDAP']['ADMINDN'], config['LDAP']['ADMINPW'])
    
    
    debug_log(4, "admin bound to ldap with dn: %s" % config['LDAP']['ADMINDN'])
    
    userdn = "uid=%s,%s" % (username, config['LDAP']['DOMAIN'])
    
    fullname = "%s %s" % (firstname, lastname)
    mailaddr = "%s@%s" % (username, config['GOOGLE']['DOMAINNAME'])

    if operation == "new":
        newuserattrs = {}
        newuserattrs['objectclass'] = ['inetOrgPerson'.encode('utf-8')]
        newuserattrs['uid'] = username.encode('utf-8')
        newuserattrs['sn'] = lastname.encode('utf-8')
        newuserattrs['givenName'] = firstname.encode('utf-8')
        newuserattrs['cn'] = fullname.encode('utf-8')
        newuserattrs['displayName'] = fullname.encode('utf-8')
        newuserattrs['userPassword'] = password.encode('utf-8')
        newuserattrs['email'] = email.encode('utf-8')
        newuserattrs['mail'] = mailaddr.encode('utf-8')
        newuserattrs['o'] = config['LDAP']['LDAPO'].encode('utf-8')
        
        ldif = ldap.modlist.addModlist(newuserattrs)
        ldapconn.add_s(userdn, ldif)
        debug_log(3, "Added %s to ldap" % username)
        
        postbody = { 
                    "fullname" : "%s %s" % (firstname, lastname),
                    "name" : username
                    }
        solveraddresponse = requests.post("%s/solvers/" % config['BIGJIMMYBOT']['APIURI'], json = postbody)
        debug_log(3, "Attempt to add %s to solvers db. Response: %s" % (username, solveraddresponse.text))
        
        #TODO:  Add solver to google
    
    if operation == "update":
        ldapconn.modify_s(userdn, 
                          [(ldap.MOD_REPLACE, 'userPassword', password.encode('utf-8'))]
                          )
        
        #TODO: update google password?

    ldapconn.unbind_s()    
    return ("OK")