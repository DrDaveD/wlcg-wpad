import os

def logmsg(host, ip, org, msg):
    full_msg = host + ' ' + ip + ' [' + str(org) + '] ' + msg
    print(full_msg.encode('ISO-8859-1'))
