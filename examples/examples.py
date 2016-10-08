#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    How to use the progression package will be demonstrated in the following examples. If you are solely interested
    usage it should suffice to go through the following. If you are searching for the actual doc
    look :doc:`here </progression>`.

    The function to monitor
    -----------------------

    Let's use ``factorial`` as an example function.

    .. literalinclude:: examples/examples.py
        :pyobject: factorial

    Any function that is supposed to be monitored by one of the classes of the progression package
    needs to have at least one argument that serves as a counter (for ``factorial`` denoted by ``c``). It needs to be a
    `sharedctype <https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.sharedctypes>`_
    because one the one hand ``factorial`` is going to change its value according to its state
    and the progress class (which runs in a subprocess) needs to access this value. For convenience progression
    provides :py:func:`progression.progress.UnsignedIntValue` which instantiates a shared unsigned int with value 0.

    ProgressBar
    -----------

    Let's use :py:class:`.progress.ProgressBar` to monitor the calculation.

    In general the following steps are necessary:

        1) setup the shared value for the counter

        2) create a ProgressBar

             * count: the shared counter
             * max_count: the maximum value counter will reach
             * interval: the refresh interval in seconds

           using the `context manager <https://docs.python.org/3/library/contextlib.html>`_ ensures
           that everything gets shutdown on exit

        3) start the ProgressBar via ``start()``

        4) trigger the calculation where ``c`` is passed to the calculating function

    .. literalinclude:: examples/examples.py
        :pyobject: run_example_ProgressBar

    The output will look like this (here without colors):

    .. code-block:: none

        2.41s [39078.4c/s] [=================>                    ] TTG 3.00s

          ^            ^                                                ^
        elapsed time   speed estimation in counts per second       time to go


    ProgressBarFancy
    ----------------

    Now we use :py:class:`.ProgressBarFancy` which provides
    slightly more information.

    Further the example shows how to use a shared type for
    the maximum value of counter, which allows to set max_count
    after the ProgressPar has started, even by the calculating function.

    .. literalinclude:: examples/examples.py
        :pyobject: run_example_ProgressBarFancy

    The output reads something like this:

    .. code-block:: none

        [TET-2s-[42877.4c/s]-TTG-3s--> 43.0%  ETA 20161008_14:04:31 ORT 5s]

        TET: total elapsed time
        TTG: time to go
        ETA: estimated time of arrival
        ORT: estimated overall running time

    ProgressBar Decorator
    ---------------------

    To quickly add a ProgressBar to an existing function the decorators from the :doc:`/decorators` ease things.

    Modification of the original ``factorial`` function as follows

    .. literalinclude:: examples/examples.py
        :pyobject: factorial_dec

    and decorating this function with
    ::

        @pr.decorators.ProgressBar

    allows for a call as in the unmonitored case
    ::

        factorial_dec(N = 200000)

    resulting in the following output

    .. code-block:: none

        factorial_dec 1.01s [61584.8c/s] [=====>    ] TTG 3.00s

    ProgressBar with no max_count value
    -----------------------------------

    When the ``max_count`` argument of the ProgressBar is ``None``
    only the elapsed time, the current speed and the value of count
    will be shown.

    .. literalinclude:: examples/examples.py
        :pyobject: run_example_max_count_is_none

    .. code-block:: none

        2.47s [38535.8c/s] #95000


    ProgressBarCounter
    ------------------

    Suppose we want to let a time consuming function run several times
    for example with different parameters. Then the :py:class:`.ProgressBarCounter`
    class counts the individual runs and estimates the speed concerning the runs. Everything on top of
    the usual monitoring.

    For doing so choose :py:class:`.ProgressBarCounter` or :py:class:`.ProgressBarFancyCounter` and trigger ``reset()`` every time
    the functions returns.

    .. literalinclude:: examples/examples.py
        :pyobject: run_example_ProgressBarCounter

    .. code-block:: none

        7.76s [20.0c/min] #2 - 1.75s [3.4c/s] [========>       ] TTG 2.00s
          ^       ^        ^      ^       ^                            ^
          1       2        3      4       5                            6

        1) total elapsed time
        2) speed of the 'resets'
        3) number of 'resets'
        4) elapsed time of current run
        5) speed of the current run
        6) time to go for the current run

    a multi ProgressBarFancy
    ------------------------

    When monitoring several processes in parallel simply replace
    count and max_count by lists of sharedctypes.

    .. literalinclude:: examples/examples.py
        :pyobject: run_example_ProgressBarFancy_multi


    .. code-block:: none

        _1_:[E-589.07ms----[20.1c/s]-G-1.00s        44.0%         O 1.59s]
        _2_:[E-906.49ms----[19.7c/s]-G-1.00s--------68.0%>        O 1.91s]
        _3_:[E-947.64ms----[20.0c/s]-G-1.00s--------76.0%------>  O 1.95s]
        _4_:[E-160.46ms--->[31.2c/s] G 1.00s        20.0%         O 1.16s]

    ProgressBar and IPython notebook
    --------------------------------

    Running any kind of ProgressBar in an IPython notebook will result in new lines
    for each status message as moving the cursor is not supported. This problem can
    be circumvented by selecting a special PipeHandler.
    ::

        progression.choose_pipe_handler('ipythonhtml')

    Doing so will forward the output from ProgressBar (any subclass of :py:class:`.Loop`) to an
    `ipywidget HTML object <http://ipywidgets.readthedocs.io/en/latest/examples/Widget%20List.html#HTML>`_.
    Such an object will be created and displayed whenever a ProgressBar gets started. The terminal style and coloring
    is converted to pure HTML.

    .. raw:: html

        <div class="jupyter-widgets widget-html"><style>.widget-html{font-family:monospace;white-space:pre}</style><span style="color:#800000">_1_:</span><span style="color:#0000ff"><b>[</b><b>E</b>-588.75ms----[23.8c/s]-<b>G</b>-1.00s--&gt;</span>  56.0%      <b>O</b> 1.59s<b><span style="color:#0000ff">]</span></b>
        <span style="color:#800000">_2_:</span><span style="color:#0000ff"><b>[</b><b>E</b>-907.35ms----[17.6c/s]-<b>G</b>-1.00s-----64.</span>0%      <b>O</b> 1.91s<b><span style="color:#0000ff">]</span></b>
        <span style="color:#800000">_3_:</span><span style="color:#0000ff"><b>[</b><b>E</b>-161</span>.35ms    [12.4c/s] <b>G</b> 2.00s      8.0%      <b>O</b> 2.16s<b><span style="color:#0000ff">]</span></b>
        <span style="color:#800000">_4_:</span><span style="color:#0000ff"><b>[</b><b>E</b>-183.51ms</span>    [21.8c/s] <b>G</b> 1.00s     16.0%      <b>O</b> 1.18s<b><span style="color:#0000ff">]</span></b>
        </div>

"""

from __future__ import division, print_function

import sys
# setup path to import progression
from os.path import abspath, dirname, split
# Add parent directory to beginning of path variable
sys.path = [split(dirname(abspath(__file__)))[0]] + sys.path

def factorial(N, c):
    f = 1
    for i in range(2, N+1):   # becasue the multiplication of two
        f *= i                # integers is faster than
        if i % 1000 == 0:     # settings the value of an sharedctype
            c.value = i       # c gets updated only every 1000 steps
    return f

def run_example_ProgressBar():
    import progression as pr
    N = 200000
    c = pr.UnsignedIntValue()            # counter for factorial
    with pr.ProgressBar(count     = c,   # (shared uint)
                        max_count = N,
                        interval  = 0.3  # the refresh time in secs.
                                         # the default is 1s
                        ) as pb:
        pb.start()                       # start progress process
        factorial(N, c)                  # doing stuff and
                                         # change the value of 'c'

def run_example_ProgressBarFancy():
    import progression as pr
    N = 200000
    c = pr.UnsignedIntValue()        # counter (shared uint)
    m = pr.UnsignedIntValue()        # the maximum value for
                                     # counter, now also shared
    with pr.ProgressBarFancy(count = c, max_count = m) as pb:
        pb.start()
        m.value = N                  # set the max_count at runtime
        factorial(N, c)


import progression as pr

@pr.decorators.ProgressBar
def factorial_dec(N,
                  c = pr.UnsignedIntValue(),
                  m = pr.UnsignedIntValue()):
    # for the decorator to work the function needs to have
    # 'c' and 'm' as arguments
    # when using default values for 'c' and 'm' the
    # function call remains the same
    m.value = N
    f = 1
    for i in range(2,N+1):
        f *= i
        if i % 1000 == 0:
            c.value = i
    return f

def run_example_ProgressBarDecorator():
    factorial_dec(N = 200000)

def run_example_max_count_is_none():
    import progression as pr
    c = pr.UnsignedIntValue()             # counter (shared uint)
    with pr.ProgressBar(count     = c,
                        max_count = None  # no maximum value of count
                                          # known
                        ) as pb:
        pb.start()
        factorial(100000, c)

def run_example_ProgressBarCounter():
    import progression as pr
    import time

    c = pr.UnsignedIntValue()       # ... the usual set up
    with pr.ProgressBarCounter(count     = c,
                               max_count = 10) as pb:
        pb.start()
        for outer_loop in [1,3,5]:        # lets crunsh the
                                          # innerloop 3 times

            for iner_loop in range(1,11): # change the counter
                c.value = iner_loop       # according to the state
                time.sleep(0.3)           # of the inner loop

            pb.reset()                    # reset the ProgressBar

def run_example_ProgressBarFancy_multi():
    import progression as pr
    import random
    import time

    def tocrunch(c, m):
        for x in range(400):
            i = random.randint(0, n - 1)
            with c[i].get_lock():        # as += operator is not
                c[i].value += 1          # atomic we need a lock
                                         # see docs.python.org
                                         # -> shared-ctypes-objects
            if c[i].value > m[i].value:  # once max_count is reached
                sbm.reset(i)             # reset the bar
            time.sleep(0.01)


    n = 4
    max_count_value = 25

    count = []          # list of shared uint
    max_count = []      # list of shared uint
    prepend = []        # list of text to prepend each bar
    for i in range(n):  # fill the lists
        count.append(pr.UnsignedIntValue(0))
        max_count.append(pr.UnsignedIntValue(max_count_value))
        prepend.append('_{}_:'.format(i + 1))

    # note: count and max_count are now lists of scharedctypes
    with pr.ProgressBarFancy(count     = count,
                             max_count = max_count,
                             interval  = 0.3,
                             prepend   = prepend,
                             width     = 60) as sbm:
        sbm.start()
        tocrunch(count, max_count)


if __name__ == "__main__":
    # import logging
    # pr.log.setLevel(logging.DEBUG)
    # run_example_ProgressBar()
    # run_example_ProgressBarFancy()
    # run_example_ProgressBarDecorator()
    # run_example_max_count_is_none()
    # run_example_ProgressBarCounter()
    # run_example_ProgressBarFancy_multi()
    pass