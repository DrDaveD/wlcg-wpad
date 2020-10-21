# Find proxies for WLCG grid site
#
# Note: log messages that have a non-empty org (the third parameter to the
#  logmsg function) are parsed for monitoring, up to a colon.

import sys, os, copy, anyjson, netaddr, threading, time, socket
from wpad_utils import *
import maxminddb

orgscachesecs = 300  # 5 minutes

workerproxiesfile = "/var/lib/wlcg-wpad/worker-proxies.json"
shoalsquidsfile = "/var/lib/wlcg-wpad/shoal-squids.json"
gireader = maxminddb.open_database("/var/lib/wlcg-wpad/geo/GeoIP2-ISP.mmdb")

orgsupdatetime = 0
orgsmodtime = 0
shoalmodtime = 0
workerorgs = {}
orgs = {}
shoalsquids = {}

# Parameters for organization cache
organizations_cache = {}  # key is IP address and value is (timestamp, organization)
organizations_cache_max_entries = 100000
organizations_cache_secs = 60*60  # 1 hour
organizations_lock = threading.Lock()


def getiporg(addr):

    cached_value = organizations_cache.get(addr)
    if cached_value:
        (timestamp, organization) = cached_value
        if time.time() <= timestamp + organizations_cache_secs:
            logmsg('-', addr, organization, 'organization came from cache')
            return organization
        else:
            # Pop expired entry from cache
            organizations_cache.pop(addr, None)
    elif len(organizations_cache) >= organizations_cache_max_entries:
        # If cache is full, remove random entry
        organizations_cache.popitem()

    with organizations_lock:
        # Recheck cache in case entry was added, while thread was waiting for a lock
        cached_value = organizations_cache.get(addr)
        if cached_value:
            logmsg('-', addr, organization, 'organization came from cache')
            return cached_value[1]

        if netaddr.IPAddress(addr).version == 6:
            try:
                hostname = socket.gethostbyaddr(addr)[0]
                ip = socket.gethostbyname(hostname)
                message = 'IPv6 address to IPv4 address translation'
            except:
                # If IPv4 could not be found, use IPv6
                ip = addr
                message = 'IPv6 address'
        else:
            ip = addr
            message = 'IPv4 address'

        organization = get_organization(ip)
        if ip != addr:
            organization_IPv6 = get_organization(addr)
            if organization == organization_IPv6:
                message = message + '. IPv6 had the same organization as IPv4'
            else:
                message = message + '. IPv6 had ' + str(organization_IPv6).encode('ISO-8859-1') + ' organization'
        organizations_cache[addr] = (int(time.time()), organization)
        logmsg('-', addr, organization, 'organization came from ' + message)

    return organization


def get_organization(ip):

    organization = None
    gir = gireader.get(ip)
    if gir is not None:
        organization = gir['organization']

    return organization


def updateorgs(host):
    global workerorgs
    global orgs
    neworgs = {}
    try:
        global orgsmodtime
        modtime = os.stat(workerproxiesfile).st_mtime
        if modtime == orgsmodtime:
            # no change
            neworgs = workerorgs
        else:
            orgsmodtime = modtime
            handle = open(workerproxiesfile, 'r')
            jsondata = handle.read()
            handle.close()
            workerproxies = anyjson.deserialize(jsondata)
    except Exception, e:
        logmsg(host, '-',  '', 'error reading ' + workerproxiesfile + ', using old: ' + str(e))
        orgsmodtime = 0
        neworgs = workerorgs

    global shoalsquids
    try:
        global shoalmodtime
        modtime = os.stat(shoalsquidsfile).st_mtime
        if modtime == shoalmodtime:
            # no change
            if neworgs == workerorgs:
                return orgs
        else:
            shoalmodtime = modtime
            handle = open(shoalsquidsfile, 'r')
            jsondata = handle.read()
            handle.close()
            shoalsquids = anyjson.deserialize(jsondata)
    except Exception, e:
        logmsg(host, '-',  '', 'error reading ' + shoalsquidsfile + ', using old: ' + str(e))
        shoalmodtime = 0
        if neworgs == workerorgs:
            return orgs

    if neworgs == {}:
        for squid in workerproxies:
            if 'ips' not in workerproxies[squid]:
                logmsg(host, '-', '', 'no ips found for ' + squid + ', skipping')
                continue
            if squid not in workerproxies[squid]['ips']:
                logmsg(host, '-', '', 'no ' + squid + ' in ips found, skipping')
                continue
            ips = workerproxies[squid]['ips'][squid]
            if not ips:
                logmsg(host, '-', '', 'ips list is empty for ' + squid + ', skipping')
                continue
            for ip in ips:
                if netaddr.IPAddress(ip).version == 4:
                    addr = ip
                    break
            else:
                addr = ips[0]
            org = getiporg(addr)
            if org is None:
                logmsg(host, '-', '', 'no org found for ' + squid + ', skipping')
                continue
            neworgs[org] = workerproxies[squid]
            if 'proxies' not in neworgs[org]:
                neworgs[org]['proxies'] = [{'default' : [ squid + ':3128' ]}]
                continue

        workerorgs = neworgs

        logmsg('-', '-', '', 'read ' + str(len(workerproxies)) + ' workerproxies and ' + str(len(neworgs)) + ' orgs')

    neworgs = copy.deepcopy(neworgs)
    numshoalsquids = 0
    numshoalorgs = 0
    numshoalduporgsquids = 0
    for squid in shoalsquids:
        shoalsquid = shoalsquids[squid]
        if 'public_ip' not in shoalsquid:
            logmsg(host, '-', '', 'no public_ip found for shoal ' + squid + ', skipping')
            continue
        ip = shoalsquid['public_ip']
        org = getiporg(ip)
        if org is None:
            logmsg(host, '-', '', 'no org found for shoal ' + squid + ', skipping')
            continue
        if org not in neworgs:
            neworgs[org] = {
                "ips": {}, 
                "names": [],
                "proxies": [ { "default": [] } ],
                "source": "shoal"
            }
            numshoalorgs += 1
        neworg = neworgs[org]
        if neworg["source"] != "shoal":
            numshoalduporgsquids += 1
            continue
        name = ""
        neworg["ips"][squid] = ip
        if "city" in shoalsquid:
            name = shoalsquid["city"]
        if "country_code" in shoalsquid:
            if name != "":
                name += "."
            name += shoalsquid["country_code"]
        if name not in neworg["names"]:
            neworg["names"].append(name)
        proxies = neworg["proxies"][0]
        if "private_ip" in shoalsquid:
            ip = shoalsquid["private_ip"]
        proxies["default"].append(ip + ":3128")
        numshoalsquids += 1
        if len(proxies["default"]) > 1:
            proxies["loadbalance"] = "proxies"
    if numshoalorgs > 0:
        logmsg('-', '-', '', 'added ' + str(numshoalsquids) + ' shoal squids in ' + str(numshoalorgs) + ' orgs')
    if numshoalduporgsquids > 0:
        logmsg('-', '-', '', 'disregarded ' + str(numshoalduporgsquids) + ' shoal squids due to overlap of org with registered squid')

    return neworgs

updatelock = threading.Lock()

def get_proxies(host, remoteip, now):
    org = getiporg(remoteip)
    if org is None:
        logmsg(host, remoteip, 'Unknown', 'no org found')
        return {'msg': 'no org found for remote ip address'}
    global orgsupdatetime
    global orgs
    updatelock.acquire()
    if orgsupdatetime < now - orgscachesecs:
        orgsupdatetime = now
        if len(orgs) > 0:
            # release lock while reading to let other threads continue
            #  to use old orgs
            updatelock.release()
            neworgs = updateorgs(host)
            updatelock.acquire()
        else:
            neworgs = updateorgs(host)
        orgs = neworgs
    if org not in orgs:
        updatelock.release()
        logmsg(host, remoteip, org, 'no squid found')
        return {'msg': 'no squid found matching the remote ip address'}
    wpadinfo = orgs[org]
    updatelock.release()
    wpadinfo = copy.deepcopy(wpadinfo)
    proxies = []
    remoteaddr = netaddr.IPAddress(remoteip)
    iprangematched = False
    idx = 0
    while idx < len(wpadinfo['proxies']):
        proxydict = wpadinfo['proxies'][idx]
        if 'ipranges' in proxydict:
            # delete the entry if the remoteaddr doesn't match
            #  one of the ipranges
            for iprange in proxydict['ipranges']:
                if remoteaddr in netaddr.IPNetwork(iprange):
                    iprangematched = True
                    if 'names' in proxydict:
                        wpadinfo['names'] = proxydict['names']
                    elif 'names' in wpadinfo:
                        del wpadinfo['names']
                    if 'cmsnames' in proxydict:
                        wpadinfo['cmsnames'] = proxydict['cmsnames']
                    elif 'cmsnames' in wpadinfo:
                        del wpadinfo['cmsnames']
                    break
            if not iprangematched:
                del wpadinfo['proxies'][idx]
                continue
        if 'default' in proxydict:
            proxies = proxydict['default']
            if len(proxies) == 0:
                logmsg(host, remoteip, org, 'no squid found')
                return {'msg': 'no squid found matching the remote ip address'}
            break
        idx += 1
    if 'disabled' in wpadinfo:
        if not iprangematched:
            logmsg(host, remoteip, org, 'disabled: ' + wpadinfo['disabled'])
            wpadinfo['proxies'] = []
            wpadinfo['msg'] = wpadinfo['disabled']
            return wpadinfo
    logmsg(host, remoteip, org, 'default squids: ' + ';'.join(proxies))
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
