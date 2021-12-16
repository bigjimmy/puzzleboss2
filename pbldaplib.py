import ldap
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
    
    return(match)
