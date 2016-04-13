# Dispatch a wpad.dat request

import wlcg_wpad
import lhchomeproxy

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

def dispatch(environ, start_response):
    if 'SERVER_NAME' not in environ:
	return bad_request(start_response, 'SERVER_NAME not set')
    if 'REMOTE_ADDR' not in environ:
	return bad_request(start_response, 'REMOTE_ADDR not set')
    proxies = ""
    host = environ['SERVER_NAME']
    remote = environ['REMOTE_ADDR']
    if host == 'lhchomeproxy.cern.ch':
	proxies = lhchomeproxy.get_proxies(remote)
    elif host == 'wlcg-wpad.cern.ch':
	proxies = wlcg_wpad.get_proxies(remote)
    else:
	return bad_request(start_response, 'Unrecognized host name')
    if proxies == "":
	return bad_request(start_response, 'No proxy found for ' + remote)
    body = 'function FindProxyForURL(url, host) {\n' + \
    	   '    return "' + proxies + '";\n' + \
	   '}'
    return good_request(start_response, body)
