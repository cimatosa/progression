#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function
import sys
# setup path to import progression
from os.path import abspath, dirname, split
# Add parent directory to beginning of path variable
sys.path = [split(dirname(abspath(__file__)))[0]] + sys.path

import progression

def factorial(N, c):
    f = 1
    for i in range(N):
        f *= i
        c.value = i
    return f

N = 10000000
c = progression.UnsignedIntValue()   # this is a python multiprocessing.Value
m = progression.UnsignedIntValue(N)  # of unsigned int type

# the progressbar need at least th shared counter 'c' and the maximum 'm'
# the context managment ensures the progressbar to stop automatically
with progression.ProgressBar(count=c, max_count=m, interval=0.3) as pb:
    pb.start()                       # show the progressbar
    factorial(N, c)                  # doing stuff and cnage the value of 'c'

with progression.ProgressBarFancy(count=c, max_count=m, interval=0.3) as pb:
    pb.start()
    factorial(N, c)

@progression.decorators.ProgressBar  # for the decorator to work
                                     # the function need to have 'c' and 'm' as arguments
def factorial_dec(N, c, m):
    f = 1
    for i in range(N):
        f *= i
        c.value = i
    return f

factorial_dec(N, c, m)
