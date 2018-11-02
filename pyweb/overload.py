# calculate the load on each org

import threading
from wlcg_wpad import gi
from wpad_utils import *

orgcleanminutes = 5

orgcleantime = 0

# Minute records keep track of the number of requests in each minute
class MinuteRecord:
    def __init__(self, now, older):
        self.minute = now               # minute of the record
        self.requests = 0               # number of requests this minute
        self.next = None                # next MinuteRecord
        if older != None:
            older.next = self           # point older record to this one

class OrgData:
    def __init__(self):
        self.lock = threading.Lock()    # lock for this org
        self.overloadminute = 0         # minute last overload triggered
        self.total = 0                  # total number of requests tracked
        self.newest = None              # newest MinuteRecord
        self.oldest = None              # oldest MinuteRecord

orgdata = {}
# lock for adding, deleting, and looking up an org
orgdatalock = threading.Lock()

# return double of org name and percent of limit in the last minutes
def orgload(remoteip, limit, minutes, persist, now):
    global orgcleantime
    org = gi.org_by_addr(remoteip)
    if org == None:
        return None, 0, 0
    now = now / 60  # this function deals only with minutes
    orgdatalock.acquire()
    if orgcleantime <= now - orgcleanminutes:
        # clean out orgs that have had no updates in minutes or overload in
        #   persist minutes, except current org
        orgcleantime = now
        numorgs = 0
        delorgs = 0
        for oldorg in list(orgdata):
            numorgs += 1
            if org == oldorg:
                continue
            data = orgdata[oldorg]
            if persist < now - data.overloadminute and \
                    data.newest.minute < now - minutes:
                del orgdata[oldorg]
                delorgs += 1
        if delorgs > 0:
            orgdatalock.release()
            logmsg('-', '-', 'cleaned load data from ' + str(delorgs) + ' orgs, ' + str(numorgs-delorgs) + ' still active')
            orgdatalock.acquire()
    # get the data for this org
    if org in orgdata:
        data = orgdata[org]
    else:
        data = OrgData()
        orgdata[org] = data
    orgdatalock.release()
    data.lock.acquire()
    # remove any minute records that are too old
    record = data.oldest
    while record != None and record.minute <= now - minutes:
        data.total -= record.requests
        record = record.next
        data.oldest = record
    record = data.newest
    if record == None or record.minute != now:
        # add new minute record
        record = MinuteRecord( now, record )
        data.newest = record
        if data.oldest == None:
            data.oldest = record
    # add one to this minute and the total
    record.requests += 1
    data.total = data.total + 1
    percent = int(data.total * 100.0 / limit)
    if percent > 100:
        data.overloadminute = now
    overloadminute = data.overloadminute
    data.lock.release()
    
    return ( org, persist - (now - overloadminute), percent )
