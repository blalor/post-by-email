# -*- encoding: utf-8 -*-

## with help from http://amix.dk/blog/post/19531

import fcntl
import errno
import time
from contextlib import contextmanager


class LockTimeout(Exception):
    pass


@contextmanager
def file_lock(lock_file, wait=0, pause=1):
    end = time.time() + wait

    with open(lock_file, "w") as fp:
        while True:
            try:
                fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)

                ## got lock!
                yield

                ## break out of loop
                break
            except IOError, e:
                if e.errno == errno.EWOULDBLOCK:
                    ## already locked
                    pass
                else:
                    raise

            if time.time() < end:
                time.sleep(pause)
            else:
                raise LockTimeout("failed to acquire lock on " + lock_file)
