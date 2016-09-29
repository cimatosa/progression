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
c = progression.UnsignedIntValue()
m = progression.UnsignedIntValue(N)

with progression.ProgressBar(count=c, max_count=m, interval=0.3) as pb:
    pb.start()
    f = factorial(N, c)

with progression.ProgressBarFancy(count=c, max_count=m, interval=0.3) as pb:
    pb.start()
    f = factorial(N, c)

