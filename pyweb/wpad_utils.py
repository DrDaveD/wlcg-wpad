import os

mypid = '[' + str(os.getpid()) + ']'
def logmsg(host, ip, msg):
    print host + mypid + ' ' + ip + ' ' + msg
