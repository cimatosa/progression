#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function
import sys
# setup path to import progression
from os.path import abspath, dirname, split
# Add parent directory to beginning of path variable
sys.path = [split(dirname(abspath(__file__)))[0]] + sys.path

import progression
import time
import random

n = 4
max_count_value = 25

count     = []      # list of shared unsigned int object
max_count = []      # list of shared unsigned int object
prepend   = []      # list of text to prepend each bar
for i in range(n):  # fill the lists
    count.append(progression.UnsignedIntValue(0))
    max_count.append(progression.UnsignedIntValue(max_count_value))
    prepend.append('_{}_:'.format(i+1))

with progression.ProgressBarCounterFancy(count     = count,
                                         max_count = max_count,
                                         interval  = 0.3,        # the refresh interval in sec
                                         prepend   = prepend) as sbm:
    sbm.start()

    for x in range(400):
        i = random.randint(0, n-1)
        with count[i].get_lock():            # as += operator is not atomic we need a lock
            count[i].value += 1              # see docs.python.org -> multiprocessing -> shared-ctypes-objects
        if count[i].value > max_count_value: # once the max value is reached
            sbm.reset(i)                     # reset the bar, increment counter
                                             # and start over
        time.sleep(0.01)
