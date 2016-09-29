progression
===========

[![PyPI version](https://badge.fury.io/py/progression.svg)](https://badge.fury.io/py/progression)
[![Build Status](https://travis-ci.org/cimatosa/progress.svg?branch=master)](https://travis-ci.org/cimatosa/progress)
[![codecov](https://codecov.io/gh/cimatosa/progress/branch/master/graph/badge.svg)](https://codecov.io/gh/cimatosa/progress)

An advanced progress bar in ASCII art which features
  * speed and estimated time of arrival
  * multiple bars
  * auto adjustment to the available terminal width
  
### Examples

##### example_simple.py

```python
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
 ```

yields

    2.71s [1896375.0c/s] [=======================>                     ] TTG 3.00s

using ``progression.ProgressBarFancy`` instead results in

    TET-4.81s-[1681289.0c/s]-TTG-2.00s----81.0%----ETA-20160929_23:02:04 ORT 6.81s

Run the example yourself to see the actual colored version of that.

Using a function decorator makes things even more simple:

```python
@progression.decorators.ProgressBar  # for the decorator to work
                                     # the function need to have 'c' and 'm' as arguments
def factorial_dec(N, c, m):
    f = 1
    for i in range(N):
        f *= i
        c.value = i
    return f

factorial_dec(N, c, m)
```

    factorial_dec 4.01s [1776754.0c/s] [======================>        ] TTG 2.00s

##### example_multi.py
```python
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
            count[i].value += 1              # see docs.python.org -> multiprocessing 
                                             # -> shared-ctypes-objects
        if count[i].value > max_count_value: # once the max value is reached
            sbm.reset(i)                     # reset the bar, increment counter
                                             # and start over
        time.sleep(0.01)
```

will show
 
    _0_:4.11s  [56.5c/min] #3 [E-924.93ms----[19.5c/s]-G-1.00s----72.0%     O 1.92s]
    _1_:4.11s  [53.1c/min] #3 [E-722.90ms----[22.1c/s]-G-1.00s--->64.0%     O 1.72s]
    _2_:4.11s     [1.2c/s] #4 [E-652.31ms----[27.6c/s]-G-1.00s----72.0%     O 1.65s]
    _3_:4.12s  [49.0c/min] #3 [E-438.79ms----[22.8c/s] G 1.00s    40.0%     O 1.44s] 


### Documentation
still missing, sorry for that
