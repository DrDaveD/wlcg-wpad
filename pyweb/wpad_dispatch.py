# Dispatch a wpad.dat request
# If the URL ends with ?ip=ADDR then use ADDR instead of $REMOTE_ADDR

import sys, urlparse, copy, time, threading
import wlcg_wpad
from wpad_utils import *
import geosort

confcachetime = 300  # 5 minutes

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
        newconf = {}
        for line in open(wlcgwpadconffile, 'r').read().split('\n'):
            line = line.split('#',1)[0]  # removes comments
            words = line.split(None,1)
            if len(words) < 2:
                continue
            key = words[0]
            equal = words[1].find('=')
            if equal <= 0:
                continue
            if key not in newconf:
                newconf[key] = {}
            name = words[1][0:equal]
            value = words[1][equal+1:]
            if len(value) == 0:
                # there was no '='; enter name as an empty list
                newconf[key][name] = []
                continue
            values = value.split(',')
            idx = 0
            while idx < len(values):
                value = values[idx]
                if value in newconf[key]:
                    if key == 'destshexps':
                        # keep track of destalias substitutions in reverse,
                        #  for the implementation of backupproxies
                        if '_destsubs' not in newconf:
                            newconf['_destsubs'] = {}
                        if value not in newconf['_destsubs']:
                            newconf['_destsubs'][value] = []
                        newconf['_destsubs'][value].append(name)

                    # replace value with list from previously defined name
                    newvalues = newconf[key][value]
                    values[idx:idx+1] = newvalues
                    idx += len(newvalues)
                else:
                    idx += 1
            newconf[key][name] = values
        conf = newconf
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
        if hostproxies[0] == 'WLCG' or hostproxies[0] == 'WLCG+BACKUP':
            wpadinfo = wlcg_wpad.get_proxies(host, remoteip, now)
            if 'msg' in wpadinfo:
                msg = wpadinfo['msg']
            if 'proxies' not in wpadinfo:
                if len(hostproxies) == 1:
                    return bad_request(start_response, host, remoteip, str(msg))
                del hostproxies[0]
                logmsg(host, remoteip, 'WLCG proxy not found, falling back')
            elif (hostproxies[0] == 'WLCG+BACKUP') and ('destshexps' in conf) \
                        and ('backupproxies' in conf):
                backups = {}
                backupdests = []
                for backupalias in conf['backupproxies']:
                    if backupalias not in conf['destshexps']:
                        continue
                    proxies, msg = geosort.sort_proxies(remoteip,
                            conf['backupproxies'][backupalias])
                    if proxies == []:
                        return bad_request(start_response, host, remoteip, msg)
                    backups[backupalias] = proxies
                    backupdests.append(backupalias + '=' + ';'.join(proxies))
                logmsg(host, remoteip, 'backup proxies are ' + ','.join(backupdests))

                newproxydicts = []
                for proxydict in wpadinfo['proxies']:
                    for backupalias in backups.keys():
                        if backupalias not in backups:
                            # it has been deleted by previous iteration, skip
                            continue
                        unibackupalias = backupalias.decode('utf-8')
                        if unibackupalias in proxydict:
                            # this is an exact matching destalias, just add
                            #  backups and we're done with this alias
                            proxydict['backups'] = backups[backupalias]
                            del backups[backupalias]
                        elif backupalias in conf['_destsubs']:
                            subs = conf['_destsubs'][backupalias]
                            gotone = False
                            for sub in subs:
                                unisub = sub.decode('utf-8')
                                if unisub in proxydict:
                                    gotone = True
                                    break
                            if gotone:
                                # matches a substitution; if all the
                                #  substitutions for this alias match a
                                #  backup alias, replace this entry with 
                                #  the backup-specific entries
                                matches = []
                                for destsub in conf['_destsubs']:
                                    if sub in conf['_destsubs'][destsub]:
                                        matches.append(destsub)
                                allmatch = True
                                for match in matches:
                                    if match not in backups:
                                        allmatch = False
                                        break
                                if allmatch:
                                    for match in matches[0:-1]:
                                        newproxydict = copy.copy(proxydict)
                                        newproxydict[match] = proxydict[unisub]
                                        del newproxydict[unisub]
                                        newproxydict['backups'] = backups[match]
                                        newproxydicts.append(newproxydict)
                                        del backups[match]
                                    match = matches[-1]
                                    proxydict[match] = proxydict[unisub]
                                    del proxydict[unisub]
                                    proxydict['backups'] = backups[match]
                                    del backups[match]

                    if u'default' in proxydict:
                        for backupalias in backups:
                            newproxydict = copy.copy(proxydict)
                            newproxydict[backupalias] = proxydict[u'default']
                            del newproxydict[u'default']
                            newproxydict['backups'] = backups[backupalias]
                            newproxydicts.append(newproxydict)
                    newproxydicts.append(proxydict)
                wpadinfo['proxies'] = newproxydicts

        if 'proxies' not in wpadinfo:
            wpadinfo['proxies'] = []
            predests = []
            while "=" in hostproxies[0]:
                # A destination_alias assigned to special proxies
                # Most often it will be just DIRECT, but can be
                #   semicolon separated
                aliasdests = hostproxies[0].split('=')
                dests = aliasdests[1].split(';')
                wpadinfo['proxies'].append({aliasdests[0] : dests})
                predests.append(hostproxies[0])
                del hostproxies[0]
            proxies, msg = geosort.sort_proxies(remoteip, hostproxies)
            if proxies == []:
                return bad_request(start_response, host, remoteip, msg)
            wpadinfo['proxies'].append({'default' : proxies})
            logmsg(host, remoteip, 'sorted squids are ' + ','.join(predests + proxies))
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
        backups = []
        if 'backups' in proxydict:
            backups = proxydict['backups']
        numproxies = len(proxies)
        if balance and numproxies > 1:
            # insert different orderings based on a random number
            # leave the default ordering as the last case (without an if)
            doubleproxies = proxies + proxies
            proxystr += indent + 'ran = Math.random();\n'
            for i in range(1, numproxies):
                cutoff = str(1.0 * i / numproxies)
                proxystr += indent + 'if (ran < ' + cutoff + ') '
                proxystr += getproxystr(doubleproxies[i:i+numproxies]+backups)
        proxystr += indent + getproxystr(proxies+backups)
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
