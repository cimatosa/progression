# -*- coding: utf-8 -*-

__version__ = '0.1.3'

"""
Progression
===========

An advanced progress bar in ASCII art which features

  * speed and estimated time of arrival
  * multiple bars
  * auto adjustment to the available terminal width
  * IPython notebook html output available

If you have one or more time consuming processes running and want to keep track of the current state,
get an estimate on when the process is going to finish
or if you just like statistics this package does the job.

.. raw:: html

    <div class="jupyter-widgets widget-html">
    <style>.widget-html{font-family:monospace;
                        color: #c0c0c0;
                        white-space:pre;
                        background-color:black}</style>
    <span style="color:#800000">  _1_:</span><span style="color:#00ff00"><b>[</b><b>E</b>-588.75ms----[23.8c/s]-<b>G</b>-1.00s--&gt;</span>  56.0%      <b>O</b> 1.59s<b><span style="color:#00ff00">]</span></b>
    <span style="color:#800000">  _2_:</span><span style="color:#00ff00"><b>[</b><b>E</b>-907.35ms----[17.6c/s]-<b>G</b>-1.00s-----64.</span>0%      <b>O</b> 1.91s<b><span style="color:#00ff00">]</span></b>
    <span style="color:#800000">  _3_:</span><span style="color:#00ff00"><b>[</b><b>E</b>-161</span>.35ms    [12.4c/s] <b>G</b> 2.00s      8.0%      <b>O</b> 2.16s<b><span style="color:#00ff00">]</span></b>
    <span style="color:#800000">  _4_:</span><span style="color:#00ff00"><b>[</b><b>E</b>-183.51ms</span>    [21.8c/s] <b>G</b> 1.00s     16.0%      <b>O</b> 1.18s<b><span style="color:#00ff00">]</span></b>
    <br>
    </div>
    <br>

It is pure python. It runs with python version 2 and 3. If you have IPython (and ipywidgets) installed and enable
the widgets extension
::

    jupyter nbextension enable --py --sys-prefix widgetsnbextension

an html variant of the ASCII art progress is available.

Getting progression:
--------------------

use the `latest version from PyPi <https://pypi.python.org/pypi/progression>`_ via
::

    pip install progression

or grab the master branch from the `GitHub repo <https://github.com/cimatosa/progression>`_
which should in principle be stable
::

    git clone https://github.com/cimatosa/progression.git

Feedback:
---------

feel free to drop a line in the `GitHub Issue section <https://github.com/cimatosa/progression/issues>`_
"""

from .progress import *
from . import decorators
