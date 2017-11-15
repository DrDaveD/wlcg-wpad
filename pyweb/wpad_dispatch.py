# Dispatch a wpad.dat request
# If the URL ends with ?ip=ADDR then use ADDR instead of $REMOTE_ADDR

import sys, urlparse, copy, time, threading
import wlcg_wpad
from wpad_utils import *
import geosort

wlcgwpadconffile = '/var/lib/wlcg-wpad/wlcgwpad.conf'

def error_request(start_response, response_code, response_body):
    response_body = response_body + '\n'
    start_response(response_code,
                   [('Cache-control', 'max-age=0'),
                    ('Content-Length', str(len(response_body)))])
    return [response_body]

def bad_request(start_response, host, ip, reason):
    response_body = 'Bad Request: ' + reason
    logmsg(host, ip, 'bad request: ' + reason)
    return error_request(start_response, '400 Bad Request', response_body)

def good_request(start_response, response_body):
    response_code = '200 OK'
    start_response(response_code,
                  [('Content-Type', 'text/plain'),
                   ('Cache-control', 'max-age=0'),
                   ('Content-Length', str(len(response_body)))])
    return [response_body]

conf = {}
confupdatetime = 0
confcachetime = 300  # 5 minutes
confmodtime = 0

def parse_wlcgwpad_conf():
    global conf
    global confmodtime
    try:
        modtime = os.stat(wlcgwpadconffile).st_mtime
        if modtime == confmodtime:
            # no change
            return
        confmodtime = modtime
	logmsg('-', '-', 'reading ' + wlcgwpadconffile)
        conf = {}
	for line in open(wlcgwpadconffile, 'r').read().split('\n'):
            line = line.split('#',1)[0]  # removes comments
	    words = line.split(None,1)
	    if len(words) < 2:
                continue
            key = words[0]
            equal = words[1].find('=')
            if equal <= 0:
                continue
            if key not in conf:
                conf[key] = {}
            name = words[1][0:equal]
            value = words[1][equal+1:]
            if len(value) == 0:
                # there was no '='; enter name as an empty list
                conf[key][name] = []
                continue
            values = value.split(',')
            idx = 0
            while idx < len(values):
                value = values[idx]
                if value in conf[key]:
                    # replace value with list from previously defined name
                    newvalues = conf[key][value]
                    values[idx:idx+1] = newvalues
                    idx += len(newvalues)
                else:
                    idx += 1
            conf[key][name] = values
    except Exception, e:
	logmsg('-', '-', 'error reading ' + wlcgwpadconffile + ', continuing: ' + str(e))
        confmodtime = 0
    return

# return a proxy auto config statement that returns a list of proxies
def getproxystr(proxies):
    proxystr = ""
    for proxy in proxies:
        if proxystr != "":
            proxystr += "; "
        proxy = str(proxy)
        if proxy == "DIRECT":
            proxystr += proxy
        else:
            proxystr += "PROXY http://" + proxy
            if proxy.find(':') == -1:
                proxystr += ":3128"
    return 'return "' + proxystr + '";\n'

def dispatch(environ, start_response):
    if 'SERVER_NAME' not in environ:
	return bad_request(start_response, 'wpad-dispatch', '-', 'SERVER_NAME not set')
    if 'REMOTE_ADDR' not in environ:
	return bad_request(start_response, 'wpad-dispatch', '-', 'REMOTE_ADDR not set')
    host = environ['SERVER_NAME']
    remoteip = environ['REMOTE_ADDR']
    if 'QUERY_STRING' in environ:
	parameters = urlparse.parse_qs(environ['QUERY_STRING'])
	if 'ip' in parameters:
	    # for testing
	    remoteip = parameters['ip'][0]
    msg = None
    now = int(time.time())
    global confupdatetime
    lock = threading.Lock()
    lock.acquire()
    if (now - confupdatetime) > confcachetime:
	confupdatetime = now
        lock.release()
        parse_wlcgwpad_conf()
    else:
        lock.release()

    wpadinfo = {}
    if ('hostproxies' in conf) and (host in conf['hostproxies']):
        hostproxies = copy.copy(conf['hostproxies'][host])
        if hostproxies[0] == 'WLCG':
            wpadinfo = wlcg_wpad.get_proxies(host, remoteip, now)
            if 'msg' in wpadinfo:
                msg = wpadinfo['msg']
            if 'proxies' not in wpadinfo:
                if len(hostproxies) == 1:
                    return bad_request(start_response, host, remoteip, str(msg))
                del hostproxies[0]
                logmsg(host, remoteip, 'WLCG proxy not found, falling back')
        if 'proxies' not in wpadinfo:
            wpadinfo['proxies'] = []
            while "=" in hostproxies[0]:
                # A destination_alias assigned to special proxies
                # Most often it will be just DIRECT, but can be
                #   semicolon separated
                aliasdests = hostproxies[0].split('=')
                dests = aliasdests[1].split(';')
                wpadinfo['proxies'].append({aliasdests[0] : dests})
                del hostproxies[0]
            proxies, msg = geosort.sort_proxies(remoteip, hostproxies)
            if proxies == []:
                return bad_request(start_response, host, remoteip, msg)
            wpadinfo['proxies'].append({'default' : proxies})
            logmsg(host, remoteip, 'sorted squids are ' + ';'.join(proxies))
    else:
        return bad_request(start_response, host, remoteip, 'Unrecognized host name')

    proxies = []
    proxystr = ""
    dests = {}
    for proxydict in wpadinfo['proxies']:
        if 'loadbalance' in proxydict and proxydict['loadbalance'] == 'proxies':
            balance = True
        else:
            balance = False
        if 'default' in proxydict:
            indent = '    '
            proxies = proxydict['default']
        elif 'destshexps' in conf:
            gotone = False
            for dest in conf['destshexps']:
                if (dest in proxydict) and (dest not in dests):
                    dests[dest] = None
                    gotone = True
                    proxies = proxydict[dest]
                    shexps = conf['destshexps'][dest]
                    exp = ''
                    for shexp in shexps:
                        if exp != '':
                            exp += ' || '
                        exp += 'shExpMatch(url, "' + shexp + '")'
                    proxystr += '    if (' + exp + ') {\n'
                    break
            if not gotone:
                continue
            indent = '        '
        else:
            continue
        numproxies = len(proxies)
        if balance and numproxies > 1:
            # insert different orderings based on a random number
            # leave the default ordering as the last case (without an if)
            doubleproxies = proxies + proxies
            proxystr += indent + 'ran = Math.random();\n'
            for i in range(1, numproxies):
                cutoff = str(1.0 * i / numproxies)
                proxystr += indent + 'if (ran < ' + cutoff + ') '
                proxystr += getproxystr(doubleproxies[i:i+numproxies])
        proxystr += indent + getproxystr(proxies)
        if 'default' in proxydict:
            break
        proxystr += '    }\n'
    if proxies == []:
        if 'msg' in wpadinfo:
            msg = str(wpadinfo['msg'])
        else:
            msg = 'No default proxy found for ' + remoteip
	return bad_request(start_response, host, remoteip, msg)
    body = 'function FindProxyForURL(url, host) {\n' + \
    	   proxystr + \
	   '}\n'
    if msg is not None:
        body = '// ' + str(msg) + '\n' + body
    return good_request(start_response, body)
