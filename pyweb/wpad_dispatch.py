# Dispatch a wpad.dat request

import wlcg_wpad
import geosort

def error_request(start_response, response_code, response_body):
    response_body = response_body + '\n'
    start_response(response_code,
                   [('Cache-control', 'max-age=0'),
                    ('Content-Length', str(len(response_body)))])
    return [response_body]

def bad_request(start_response, reason):
    response_body = 'Bad Request: ' + reason
    return error_request(start_response, '400 Bad Request', response_body)

def good_request(start_response, response_body):
    response_code = '200 OK'
    start_response(response_code,
                  [('Content-Type', 'text/plain'),
                   ('Cache-control', 'max-age=0'),
                   ('Content-Length', str(len(response_body)))])
    return [response_body]

def parse_geosort_conf():
    hostproxies = []
    for line in open('/etc/wlcg-wpad/geosort.conf', 'r').read().split('\n'):
        words = line.split()
        if words:
            if words[0] == 'hostproxies':
                parts = words[1].split('=')
                proxies = parts[1].split(',')
                hostproxies.append([parts[0], proxies])
    return hostproxies

hostproxies = parse_geosort_conf()

def dispatch(environ, start_response):
    if 'SERVER_NAME' not in environ:
	return bad_request(start_response, 'SERVER_NAME not set')
    if 'REMOTE_ADDR' not in environ:
	return bad_request(start_response, 'REMOTE_ADDR not set')
    proxies = []
    host = environ['SERVER_NAME']
    remoteip = environ['REMOTE_ADDR']
    if host == 'wlcg-wpad.cern.ch':
	proxies = wlcg_wpad.get_proxies(remoteip)
    else:
        gotone = False
        for hostproxy in hostproxies:
            if host == hostproxy[0]:
                gotone = True
                proxies, errmsg = geosort.sort_proxies(remoteip, hostproxy[1])
                if errmsg != None:
                    return bad_request(start_response, errmsg)
		break
        if not gotone:
            return bad_request(start_response, 'Unrecognized host name')
    if proxies == []:
	return bad_request(start_response, 'No proxy found for ' + remoteip)
    proxystr = ""
    for proxy in proxies:
	if proxystr != "":
	    proxystr += "; "
	proxystr += "PROXY http://" + proxy
	if proxy.find(':') == -1:
	    proxystr += ":3128"
    body = 'function FindProxyForURL(url, host) {\n' + \
    	   '    return "' + proxystr + '"\n' + \
	   '}'
    return good_request(start_response, body)
