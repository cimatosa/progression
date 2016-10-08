# -*- coding: utf-8 -*-

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

It is pure python. It runs with python version 2 and 3. If you have IPython (and ipywidgets) installed and enable
the widgets extension
::

    jupyter nbextension enable --py --sys-prefix widgetsnbextension

an html variant of the ASCII art progress is available.

Getting progression:
-------------------

use the `latest version from PyPi <https://pypi.python.org/pypi/progression>`_ via
::

    pip install progression

or grab the master branch from the `GitHub repo <https://github.com/cimatosa/progression>`_
which should in principle be stable
::

    git clone https://github.com/cimatosa/progression.git

Feedback:
--------

feel free to drop a line in the `GitHub Issue section <https://github.com/cimatosa/progression/issues>`_
"""

from .progress import *
from . import decorators