#! /usr/bin/env python

import wlcg_wpad

def application(environ, start_response):

    return wlcg_wpad.dispatch(environ, start_response)
