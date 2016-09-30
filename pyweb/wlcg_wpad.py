# Find proxies for WLCG grid site

import sys, os, copy, time, anyjson, netaddr
from wpad_utils import *
import GeoIP

cachetime = 300  # 5 minutes

workerproxiesfile = "/var/lib/wlcg-wpad/worker-proxies.json"
gi = GeoIP.open("/var/lib/wlcg-wpad/geo/GeoIPOrg.dat", GeoIP.GEOIP_STANDARD)

orgsupdatetime = 0
orgsmodtime = 0
orgs = {}
squidorgs = {}

def updateorgs(host):
    try:
	global orgsmodtime
	modtime = os.stat(workerproxiesfile).st_mtime
	if modtime == orgsmodtime:
	    # no change
	    return
	orgsmodtime = modtime
	handle = open(workerproxiesfile, 'r')
	jsondata = handle.read()
	handle.close()
	workerproxies = anyjson.deserialize(jsondata)
    except Exception, e:
	logmsg(host, '-',  'error reading ' + workerproxiesfile + ', using old: ' + str(e))
	return

    for squid in workerproxies:
        if 'ip' not in workerproxies[squid]:
            logmsg(host, '-', 'no ip for ' + squid + ', skipping')
            continue
        org = gi.org_by_addr(workerproxies[squid]['ip'])
        if org is None:
            logmsg(host, '-', 'no org for ' + squid + ', skipping')
            continue
        squidorgs[squid] = org
        orgs[org] = workerproxies[squid]
        if 'proxies' not in orgs[org]:
            orgs[org]['proxies'] = [{'default' : [ squid + ':3128' ]}]
            continue

    logmsg('-', '-', 'read ' + str(len(workerproxies)) + ' workerproxies, ' + str(len(squidorgs)) + ' squidorgs and ' + str(len(orgs)) + ' orgs')

def get_proxies(host, remoteip):
    global orgsupdatetime
    now = int(time.time())
    if (now - orgsupdatetime) > cachetime:
	orgsupdatetime = now
	updateorgs(host)
    org = gi.org_by_addr(remoteip)
    if org is None:
	logmsg(host, remoteip, 'no org found for ip address')
	return {'msg': 'no org found for remote ip address'}
    if org not in orgs:
	logmsg(host, remoteip, 'no squid found for org ' + org)
	return {'msg': 'no squid found matching the remote ip address'}
    wpadinfo = copy.deepcopy(orgs[org])
    if 'disabled' in wpadinfo:
	logmsg(host, remoteip, 'disabled: ' + wpadinfo['disabled'])
        wpadinfo['proxies'] = []
        wpadinfo['msg'] = wpadinfo['disabled']
        return wpadinfo
    proxies = []
    remoteaddr = netaddr.IPAddress(remoteip)
    idx = 0
    for proxydict in wpadinfo['proxies']:
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
