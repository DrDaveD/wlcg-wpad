# Find proxies for WLCG grid site

import sys, os, time, anyjson
from wpad_utils import *
import GeoIP

cachetime = 300  # 5 minutes

gridsquidsfile = "/var/lib/wlcg-wpad/grid-squids.json"
gi = GeoIP.open("/var/lib/wlcg-wpad/geo/GeoIPOrg.dat", GeoIP.GEOIP_STANDARD)

orgsquidsupdatetime = 0
orgsquidsmodtime = 0
orgsquids = {}
squidorgs = {}

def updateorgsquids(host):
    try:
	global orgsquidsmodtime
	modtime = os.stat(gridsquidsfile).st_mtime
	if modtime == orgsquidsmodtime:
	    # no change
	    return
	orgsquidsmodtime = modtime
	handle = open(gridsquidsfile, 'r')
	jsondata = handle.read()
	handle.close()
	gridsquids = anyjson.deserialize(jsondata)
    except Exception, e:
	logmsg(host, '-',  'error reading ' + gridsquidsfile + ', using old: ' + str(e))
	return

    added = 0
    for squid in gridsquids:
	if squid not in squidorgs:
	    org = gi.org_by_name(squid)
	    if org is None:
		logmsg(host, '-', 'no org for ' + squid + ', skipping')
		continue
	    added += 1
	    squidorgs[squid] = org
	    if org in orgsquids:
		orgsquids[org].append(squid)
	    else:
		orgsquids[org] = [ squid ]

    deleted = 0
    for squid in squidorgs:
	if squid not in gridsquids:
	    deleted += 1
	    org = squidorgs[squid]
	    del squidorgs[squid]
	    del orgsquids[org][squid]
	    if orgsquids[org] == []:
		del orgsquids[org]

    logmsg('-', '-', 'read ' + str(len(gridsquids)) + ' gridsquids, added ' + str(added) + ', deleted ' + str(deleted) + ', now have ' + str(len(squidorgs)) + ' squidorgs and ' + str(len(orgsquids)) + ' orgsquids')

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
    logmsg(host, remoteip, 'squids for org "' + org + '" are ' + ';'.join(orgsquids[org]))
    return orgsquids[org], None
