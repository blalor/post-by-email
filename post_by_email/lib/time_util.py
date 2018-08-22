# -*- encoding: utf-8 -*-

import datetime
import email.utils
import calendar


ZERO = datetime.timedelta(0)


## http://stackoverflow.com/a/23117071/53051
class FixedOffset(datetime.tzinfo):
    """Fixed UTC offset: `time = utc_time + utc_offset`."""
    def __init__(self, offset, name=None):
        self.__offset = offset
        if name is None:
            seconds = abs(offset).seconds
            assert abs(offset).days == 0
            hours, seconds = divmod(seconds, 3600)
            if offset < ZERO:
                hours = -hours
            minutes, seconds = divmod(seconds, 60)
            assert seconds == 0
            #NOTE: the last part is to remind about deprecated POSIX
            #  GMT+h timezones that have the opposite sign in the
            #  name; the corresponding numeric value is not used e.g.,
            #  no minutes
            self.__name = "<%+03d%02d>GMT%+d" % (hours, minutes, -hours)
        else:
            self.__name = name

    def utcoffset(self, dt=None):
        return self.__offset

    def tzname(self, dt=None):
        return self.__name

    def dst(self, dt=None):
        return ZERO

    def __repr__(self):
        return "FixedOffset(%r, %r)" % (self.utcoffset(), self.tzname())


UTC = FixedOffset(ZERO, "UTC")


def parse_date(date_str):
    ## timezones in python continue to be a shit-show
    ## returns datetime in the original zone
    ## http://stackoverflow.com/a/23117071/53051
    tt = email.utils.parsedate_tz(date_str)

    ## timestamp in utc
    timestamp = calendar.timegm(tt) - tt[9]
    naive_utc_dt = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=timestamp)
    aware_utc_dt = naive_utc_dt.replace(tzinfo=UTC)
    aware_dt = aware_utc_dt.astimezone(FixedOffset(datetime.timedelta(seconds=tt[9])))

    return aware_dt
