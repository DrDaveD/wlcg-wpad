import os

def logmsg(host, ip, org, msg):
    print host + ' ' + ip + ' [' + str(org).encode('ISO-8859-1') + '] ' + msg
