# Find proxies for WLCG grid site

import sys, os, copy, anyjson, netaddr, threading
from wpad_utils import *
import maxminddb

orgscachesecs = 300  # 5 minutes

workerproxiesfile = "/var/lib/wlcg-wpad/worker-proxies.json"
gireader = maxminddb.open_database("/var/lib/wlcg-wpad/geo/GeoIP2-ISP.mmdb")

orgsupdatetime = 0
orgsmodtime = 0
orgs = {}

def updateorgs(host):
    try:
        global orgsmodtime
        modtime = os.stat(workerproxiesfile).st_mtime
        if modtime == orgsmodtime:
            # no change
            return orgs
        orgsmodtime = modtime
        handle = open(workerproxiesfile, 'r')
        jsondata = handle.read()
        handle.close()
        workerproxies = anyjson.deserialize(jsondata)
    except Exception, e:
        logmsg(host, '-',  'error reading ' + workerproxiesfile + ', using old: ' + str(e))
        orgsmodtime = 0
        return orgs

    neworgs = {}
    for squid in workerproxies:
        if 'ip' not in workerproxies[squid]:
            logmsg(host, '-', 'no ip for ' + squid + ', skipping')
            continue
        org = None
        gir = gireader.get(workerproxies[squid]['ip'])
        if gir is not None:
            org = gir['organization']
        if org is None:
            logmsg(host, '-', 'no org for ' + squid + ', skipping')
            continue
        neworgs[org] = workerproxies[squid]
        if 'proxies' not in neworgs[org]:
            neworgs[org]['proxies'] = [{'default' : [ squid + ':3128' ]}]
            continue

    logmsg('-', '-', 'read ' + str(len(workerproxies)) + ' workerproxies and ' + str(len(neworgs)) + ' orgs')

    return neworgs

updatelock = threading.Lock()

def get_proxies(host, remoteip, now):
    org = None
    gir = gireader.get(remoteip)
    if gir is not None:
        org = gir['organization']
    if org is None:
        logmsg(host, remoteip, 'no org found for ip address')
        return {'msg': 'no org found for remote ip address'}
    global orgsupdatetime
    updatelock.acquire()
    if orgsupdatetime < now - orgscachesecs:
        orgsupdatetime = now
        updatelock.release()
        neworgs = updateorgs(host)
	updatelock.acquire()
        global orgs
        orgs = neworgs
    if org not in orgs:
        updatelock.release()
        logmsg(host, remoteip, 'no squid found for org ' + org)
        return {'msg': 'no squid found matching the remote ip address'}
    wpadinfo = orgs[org]
    updatelock.release()
    wpadinfo = copy.deepcopy(wpadinfo)
    if 'disabled' in wpadinfo:
        logmsg(host, remoteip, 'disabled: ' + wpadinfo['disabled'])
        wpadinfo['proxies'] = []
        wpadinfo['msg'] = wpadinfo['disabled']
        return wpadinfo
    proxies = []
    remoteaddr = netaddr.IPAddress(remoteip)
    idx = 0
    while idx < len(wpadinfo['proxies']):
        proxydict = wpadinfo['proxies'][idx]
        if 'ipranges' in proxydict:
            # delete the entry if the remoteaddr doesn't match
            #  one of the ipranges
            matchedone = False
            for iprange in proxydict['ipranges']:
                if remoteaddr in netaddr.IPNetwork(iprange):
                    matchedone = True
                    break
            if not matchedone:
                del wpadinfo['proxies'][idx]
                continue
        if 'default' in proxydict:
            proxies = proxydict['default']
            break
        idx += 1
    logmsg(host, remoteip, 'default squids for org "' + org + '" are ' + ';'.join(proxies))
    msg = ''
    if 'names' in wpadinfo:
        msg = 'For ' + ', '.join(wpadinfo['names'])
    if 'cmsnames' in wpadinfo:
        if msg != '':
            msg += '; '
        msg += 'CMS: ' + ','.join(wpadinfo['cmsnames'])
    if msg != '':
        wpadinfo['msg'] = msg
    return wpadinfo
