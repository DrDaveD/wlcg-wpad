# Find proxies for WLCG grid site

import sys, os, time, anyjson
from wpad_utils import *
import GeoIP

cachetime = 300  # 5 minutes

workerproxiesfile = "/var/lib/wlcg-wpad/worker-proxies.json"
gi = GeoIP.open("/var/lib/wlcg-wpad/geo/GeoIPOrg.dat", GeoIP.GEOIP_STANDARD)

orgsquidsupdatetime = 0
orgsquidsmodtime = 0
orgsquids = {}
squidorgs = {}
orgdisabledmsgs = {}

def updateorgsquids(host):
    try:
	global orgsquidsmodtime
	modtime = os.stat(workerproxiesfile).st_mtime
	if modtime == orgsquidsmodtime:
	    # no change
	    return
	orgsquidsmodtime = modtime
	handle = open(workerproxiesfile, 'r')
	jsondata = handle.read()
	handle.close()
	workerproxies = anyjson.deserialize(jsondata)
    except Exception, e:
	logmsg(host, '-',  'error reading ' + workerproxiesfile + ', using old: ' + str(e))
	return

    for squid in workerproxies:
        org = gi.org_by_name(squid)
        if org is None:
            logmsg(host, '-', 'no org for ' + squid + ', skipping')
            continue
        squidorgs[squid] = org
        orgsquids[org] = [ squid + ':3128' ] # default
        if 'disabled' in workerproxies[squid]:
            orgdisabledmsgs[org] = workerproxies[squid]['disabled']
            continue
        if 'proxies' not in workerproxies[squid]:
            continue
        proxydicts = workerproxies[squid]['proxies']
        for proxydict in proxydicts:
            if 'default' in proxydict:
                orgsquids[org] = proxydict['default']
                break

    logmsg('-', '-', 'read ' + str(len(workerproxies)) + ' workerproxies, ' + str(len(squidorgs)) + ' squidorgs and ' + str(len(orgsquids)) + ' orgsquids')

def get_proxies(host, remoteip):
    global orgsquidsupdatetime
    now = int(time.time())
    if (now - orgsquidsupdatetime) > cachetime:
	orgsquidsupdatetime = now
	updateorgsquids(host)
    org = gi.org_by_addr(remoteip)
    if org is None:
	logmsg(host, remoteip, 'no org found for ip address')
	return [], "no org found for remote ip address"
    if org not in orgsquids:
	logmsg(host, remoteip, 'no squid found for org ' + org)
	return [], "no squid found matching the remote ip address"
    if org in orgdisabledmsgs:
	logmsg(host, remoteip, 'disabled: ' + orgdisabledmsgs[org])
        return [], orgdisabledmsgs[org]
    logmsg(host, remoteip, 'squids for org "' + org + '" are ' + ';'.join(orgsquids[org]))
    return orgsquids[org], None
