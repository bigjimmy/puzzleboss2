import yaml
import inspect
import datetime
import bleach

with open('puzzleboss.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

def debug_log(sev, message):
    # Levels:
    # 0 = emergency
    # 1 = error
    # 2 = warning
    # 3 = info
    # 4 = debug
    # 5 = trace
    
    if config['APP']['LOGLEVEL'] >= sev:
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        print("[%s] [SEV%s] %s: %s" % (timestamp, sev, inspect.currentframe().f_back.f_code.co_name, message))
    return

def sanitize_string(mystring):
    outstring = ''.join(e for e in mystring if e.isalnum())
    return (outstring)
