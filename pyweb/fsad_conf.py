# return the body for an fsad.conf request

def getbody(remoteip, conf):
    body = 'external_ip=' + remoteip + '\n'
    if 'fsadconf' in conf:
        for var in conf['fsadconf']:
            for val in conf['fsadconf'][var]:
                body += var + '=' + val + '\n'
    return body
