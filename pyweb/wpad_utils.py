import os

def logmsg(host, ip, org, msg):
    print host + ' ' + ip + ' [' + org.encode('ISO-8859-1') + '] ' + msg
