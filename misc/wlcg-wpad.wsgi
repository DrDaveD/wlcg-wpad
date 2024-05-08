#! /usr/bin/env python3

import wpad_dispatch

def application(environ, start_response):

    return wpad_dispatch.dispatch(environ, start_response)
