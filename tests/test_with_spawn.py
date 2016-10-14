#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function

import multiprocessing as mp
try:
    mp.set_start_method('spawn')
except Exception as e:
    print("ignoring {} ({}) while trying to set mp start method to 'spawn'".format(type(e), e))
    print("mp.get_start_method reads '{}'".format(mp.get_start_method()))
    
import pytest
    
from test_progress import *
from test_decorators import *

pytest.mark.xfail(test_fork)

if __name__ == "__main__":
    test_fork()
