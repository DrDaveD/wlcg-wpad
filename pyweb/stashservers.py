# return the order of selected stashserver list followed by
# the contents of stashservers.list

import urllib.request, urllib.parse, urllib.error

stashserversfile = '/var/lib/wlcg-wpad/stashservers.whitelist'

# exceptions are caught by caller

def getbody(remoteip, parameters):
    contents = open(stashserversfile, 'rb').read()
    lists = contents.split(b'\n')[3].decode()
    lists = lists.split(';')
    listname = 'xroot'
    if 'list' in parameters:
        listname = parameters['list'][0]
    servers = ""
    for l in lists:
        n=len(listname)+1
        if l[0:n] == listname + '=':
            servers = l[n:]
            break
    if servers == "":
        raise Exception("list name '" + listname + "' unknown")

    url = 'http://localhost/api/v1.0/geo/' + remoteip + '/' + servers
    request = urllib.request.Request(url)
    order = urllib.request.urlopen(request).read()

    return order + contents
