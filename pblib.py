import yaml
import inspect
import datetime
import bleach
import smtplib
from email.message import EmailMessage

with open("puzzleboss.yaml") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

huntfolderid = "undefined"


def debug_log(sev, message):
    # Levels:
    # 0 = emergency
    # 1 = error
    # 2 = warning
    # 3 = info
    # 4 = debug
    # 5 = trace

    if config["APP"]["LOGLEVEL"] >= sev:
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        print(
            "[%s] [SEV%s] %s: %s"
            % (timestamp, sev, inspect.currentframe().f_back.f_code.co_name, message),
            flush=True
        )
    return


def sanitize_string(mystring):
    outstring = "".join(e for e in mystring if e.isalnum())
    return outstring


def email_user_verification(email, code, fullname, username):
    debug_log(4, "start for email: %s" % email);
    
    messagecontent = """Hello %s!
                        Someone using this email address has attempted to register or reset an account at
                        %s
                        username: %s
                        name: %s
                        
                        If this was you, please follow the link below or type the provided URL 
                        into a browser to complete account creation or reset process.
                        
                        %s/index.php?code=%s
                                                
                        Thank you.
                        - Puzzleboss 2000
                        
                        (replies to this email will not reach anybody)
                        """ % (email, config['LDAP']['LDAPO'], username, fullname, config['APP']['ACCT_URI'], code)
                            
    debug_log(4, "Email to be sent: %s" % messagecontent)
    
    try:
        msg = EmailMessage()
        msg['Subject'] = "Finish your %s account sign-up or reset" % config['LDAP']['LDAPO']
        msg['From'] = "puzzleboss@%s" % config['GOOGLE']['DOMAINNAME']
        msg['To'] = email
        msg.set_content(messagecontent)
        s = smtplib.SMTP(config['APP']['MAILRELAY'])
        s.send_message(msg)
        s.quit()

    except Exception as e:
        errmsg = str(e)
        debug_log(2, "Exception sending email: %s" % errmsg)
        return errmsg
    
    return "OK"

    
    
    