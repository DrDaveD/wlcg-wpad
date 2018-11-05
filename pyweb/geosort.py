# Geo-sort proxies
# Code mostly stolen from cvmfs-server's cvmfs_geo.py (which dwd also wrote).
#  Depends on data files and GeoIP library from cvmfs-server package.

import math
import string
import re
import bisect
import socket
import time
import maxminddb

gireader = maxminddb.open_database("/var/lib/cvmfs-server/geo/GeoLite2-City.mmdb")

proxygirs = {}
lookup_ttl = 60*5       # 5 minutes

# function came from http://www.johndcook.com/python_longitude_latitude.html
def distance_on_unit_sphere(lat1, long1, lat2, long2):

    if (lat1 == lat2) and (long1 == long2):
        return 0.0

    # Convert latitude and longitude to 
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0
        
    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians
        
    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians
        
    # Compute spherical distance from spherical coordinates.
        
    # For two locations in spherical coordinates 
    # (1, theta, phi) and (1, theta, phi)
    # cosine( arc length ) = 
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length
    
    cos = (math.sin(phi1)*math.sin(phi2)*math.cos(theta1 - theta2) + 
           math.cos(phi1)*math.cos(phi2))
    arc = math.acos( cos )

    # Remember to multiply arc by the radius of the earth 
    # in your favorite set of units to get length.
    return arc


def sort_proxies(rem_addr, proxies):

    gir_rem = gireader.get(rem_addr)
    if gir_rem is None:
        return [[], 'remote addr not found in database']
    gir_rem = gir_rem['location']

    idx = 0
    arcs = []
    orderedproxies = []

    onegood = False
    now = int(time.time())
    for proxy in proxies:
        colon = proxy.find(':')
        if colon == -1:
            name = proxy
            proxy += ':3128'
        else:
            name = proxy[0:colon]
        if (proxy not in proxygirs) or (proxygirs[proxy][1] < (now - lookup_ttl)):
            # Look up names periodically in case their IP values have changed
            #    even though it's unlikely their geo info has changed
            ai = ()
            try:
                ai = socket.getaddrinfo(name,80,0,0,socket.IPPROTO_TCP)
            except:
                pass

            # Try IPv4 first since that geo info is currently more reliable,
            #     and most machines today are dual stack if they have IPv6
            gir_proxy = None
            for info in ai:
                # look for IPv4 address first
                if info[0] == socket.AF_INET:
                    gir_proxy = gireader.get(info[4][0])
                    break
            if gir_proxy == None:
                # look for an IPv6 address if no IPv4 record found
                for info in ai:
                    if info[0] == socket.AF_INET6:
                        gir_proxy = gireader.get(info[4][0])
                        break
            if gir_proxy != None:
                gir_proxy = gir_proxy['location']

            if (gir_proxy is None) and (proxy in proxygirs):
                # reuse old value, there may have been a temporary DNS problem
                gir_proxy = proxygirs[proxy][0]
            proxygirs[proxy] = [gir_proxy, now]
        else:
            gir_proxy = proxygirs[proxy][0]

        if gir_proxy is None:
            # put it on the end of the list
            arc = float("inf")
        else:
            onegood = True
            arc = distance_on_unit_sphere(gir_rem['latitude'],
                                          gir_rem['longitude'],
                                          gir_proxy['latitude'],
                                          gir_proxy['longitude'])
            #print "distance between " + \
            #    rem_addr + ' (' + str(gir_rem['latitude']) + ',' + str(gir_rem['longitude']) + ')' \
            #    + " and " + \
            #    proxy + ' (' + str(gir_proxy['latitude']) + ',' + str(gir_proxy['longitude']) + ')' + \
            #    " is " + str(arc)

        i = bisect.bisect(arcs, arc)
        arcs[i:i] = [ arc ]
        orderedproxies[i:i] = [ proxy ]
        idx += 1

    if not onegood:
        # return an error if all the proxy names were bad
        return [[], 'no proxy addr found in database']

    return [orderedproxies, None]
