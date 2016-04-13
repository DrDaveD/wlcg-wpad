# Dispatch a wpad.dat request

def error_request(start_response, response_code, response_body):
    response_body = response_body + '\n'
    start_response(response_code,
                   [('Content-Length', str(len(response_body)))])
    return [response_body]

def bad_request(start_response, reason):
    response_body = 'Bad Request: ' + reason
    return error_request(start_response, '400 Bad Request', response_body)

def good_request(start_response, response_body):
    response_code = '200 OK'
    start_response(response_code,
                  [('Content-Type', 'text/plain'),
                   ('Content-Length', str(len(response_body)))])
    return [response_body]


def dispatch(environ, start_response):
    body = str(environ)
    return good_request(start_response, body)

