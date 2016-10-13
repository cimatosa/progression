# -*- coding: utf-8 -*-
from __future__ import division, print_function

import os
import sys
import subprocess as sp
import logging

try:
    from shutil import get_terminal_size as shutil_get_terminal_size
except ImportError:
    shutil_get_terminal_size = None

class MultiLineFormatter(logging.Formatter):
    """pads a multiline log message with spaces such that

     <HEAD> msg_line1
            msg_line2
             ...
    """
    def format(self, record):
        _str = logging.Formatter.format(self, record)
        header = _str.split(record.message)[0]
        _str = _str.replace('\n', '\n' + ' '*len(header))
        return _str

def_handl = logging.StreamHandler(stream = sys.stderr)          # the default handler simply uses stderr
def_handl.setLevel(logging.DEBUG)                               # ... listens to all messaged
fmt = MultiLineFormatter('%(asctime)s %(name)s %(levelname)s : %(message)s')
def_handl.setFormatter(fmt)                                     # ... and pads multiline messaged
log = logging.getLogger(__name__)                               # creates the default log for this module
log.addHandler(def_handl)

def get_terminal_size(defaultw=80):
    """ Checks various methods to determine the terminal size


    Methods:
    - shutil.get_terminal_size (only Python3)
    - fcntl.ioctl
    - subprocess.check_output
    - os.environ

    Parameters
    ----------
    defaultw : int
        Default width of terminal.


    Returns
    -------
    width, height : int
        Width and height of the terminal. If one of them could not be
        found, None is return in its place.

    """
    if hasattr(shutil_get_terminal_size, "__call__"):
        return shutil_get_terminal_size()
    else:
        try:
            import fcntl, termios, struct
            fd = 0
            hw = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,
                                                 '1234'))
            return (hw[1], hw[0])
        except:
            try:
                out = sp.check_output(["tput", "cols"])
                width = int(out.decode("utf-8").strip())
                return (width, None)
            except:
                try:
                    hw = (os.environ['LINES'], os.environ['COLUMNS'])
                    return (hw[1], hw[0])
                except:
                    return (defaultw, None)


def get_terminal_width(default=80, name=None):
    try:
        width = get_terminal_size(defaultw=default)[0]
    except:
        width = default
    return width


def terminal_reserve(progress_obj, terminal_obj=None, identifier=None):
    """ Registers the terminal (stdout) for printing.

    Useful to prevent multiple processes from writing progress bars
    to stdout.

    One process (server) prints to stdout and a couple of subprocesses
    do not print to the same stdout, because the server has reserved it.
    Of course, the clients have to be nice and check with
    terminal_reserve first if they should (not) print.
    Nothing is locked.

    Returns
    -------
    True if reservation was successful (or if we have already reserved this tty),
    False if there already is a reservation from another instance.
    """
    if terminal_obj is None:
        terminal_obj = sys.stdout

    if identifier is None:
        identifier = ''

    if terminal_obj in TERMINAL_RESERVATION:  # terminal was already registered
        log.debug("this terminal %s has already been added to reservation list", terminal_obj)

        if TERMINAL_RESERVATION[terminal_obj] is progress_obj:
            log.debug("we %s have already reserved this terminal %s", progress_obj, terminal_obj)
            return True
        else:
            log.debug("someone else %s has already reserved this terminal %s", TERMINAL_RESERVATION[terminal_obj],
                      terminal_obj)
            return False
    else:  # terminal not yet registered
        log.debug("terminal %s was reserved for us %s", terminal_obj, progress_obj)
        TERMINAL_RESERVATION[terminal_obj] = progress_obj
        return True


def terminal_unreserve(progress_obj, terminal_obj=None, verbose=0, identifier=None):
    """ Unregisters the terminal (stdout) for printing.

    an instance (progress_obj) can only unreserve the tty (terminal_obj) when it also reserved it

    see terminal_reserved for more information

    Returns
    -------
    None
    """

    if terminal_obj is None:
        terminal_obj = sys.stdout

    if identifier is None:
        identifier = ''
    else:
        identifier = identifier + ': '

    po = TERMINAL_RESERVATION.get(terminal_obj)
    if po is None:
        log.debug("terminal %s was not reserved, nothing happens", terminal_obj)
    else:
        if po is progress_obj:
            log.debug("terminal %s now unreserned", terminal_obj)
            del TERMINAL_RESERVATION[terminal_obj]
        else:
            log.debug("you %s can NOT unreserve terminal %s be cause it was reserved by %s", progress_obj, terminal_obj,
                      po)

def len_string_without_ESC(s):
    return len(remove_ESC_SEQ_from_string(s))

def remove_ESC_SEQ_from_string(s):
    old_idx = 0
    new_s = ""
    ESC_CHAR_START = "\033["
    while True:
        idx = s.find(ESC_CHAR_START, old_idx)
        if idx == -1:
            break
        j = 2
        while s[idx+j] in '0123456789':
            j += 1

        new_s += s[old_idx:idx]
        old_idx = idx+j+1

    new_s += s[old_idx:]
    return new_s

    # for esc_seq in ESC_SEQ_SET:
    #     s = s.replace(esc_seq, '')
    # return s

def _close_kind(stack, which_kind):
    stack_tmp = []
    s = ""

    # close everything until which_kind is found
    while True:
        kind, start, end = stack.pop()
        if kind != which_kind:
            s += end
            stack_tmp.append((kind, start, end))
        else:
            break

    # close which_kind
    s = end

    # start everything that was closed before which_kind
    for kind, start, end in stack_tmp:
        s += start
        stack.append((kind, start, end))

    return s

def _close_all(stack):
    s = ""
    for kind, start, end in stack:
        s += end
    return s

def _open_color(stack, color):
    start = '<span style="color:{}">'.format(color)
    end = '</span>'
    stack.append(('color', start, end))
    return start

def _open_bold(stack):
    start = '<b>'
    end = '</b>'
    stack.append(('bold', start, end))
    return start

def ESC_SEQ_to_HTML(s):
    old_idx = 0
    new_s = ""
    ESC_CHAR_START = "\033["
    color_on = False
    bold_on = False
    stack = []
    while True:
        idx = s.find(ESC_CHAR_START, old_idx)
        if idx == -1:
            break
        j = 2
        while s[idx + j] in '0123456789':
            j += 1

        new_s += s[old_idx:idx]
        old_idx = idx + j + 1
        escseq = s[idx:idx+j+1]

        if escseq in ESC_COLOR_TO_HTML:  # set color
            if color_on:
                new_s += _close_kind(stack, which_kind = 'color')
            new_s += _open_color(stack, ESC_COLOR_TO_HTML[escseq])
            color_on = True
        elif escseq == ESC_DEFAULT:      # unset color
            if color_on:
                new_s += _close_kind(stack, which_kind = 'color')
                color_on = False
        elif escseq == ESC_BOLD:
            if not bold_on:
                new_s += _open_bold(stack)
                bold_on = True
        elif escseq == ESC_RESET_BOLD:
            if bold_on:
                new_s += _close_kind(stack, which_kind = 'bold')
                bold_on = False
        elif escseq == ESC_NO_CHAR_ATTR:
            if color_on:
                new_s += _close_kind(stack, which_kind = 'color')
                color_on = False
            if bold_on:
                new_s += _close_kind(stack, which_kind = 'bold')
                bold_on = False
        else:
            pass

    new_s += s[old_idx:]
    new_s += _close_all(stack)

    return new_s

def ESC_MOVE_LINE_UP(n):
    return "\033[{}A".format(n)


def ESC_MOVE_LINE_DOWN(n):
    return "\033[{}B".format(n)

ESC_NO_CHAR_ATTR  = "\033[0m"

ESC_BOLD          = "\033[1m"
ESC_DIM           = "\033[2m"
ESC_UNDERLINED    = "\033[4m"
ESC_BLINK         = "\033[5m"
ESC_INVERTED      = "\033[7m"
ESC_HIDDEN        = "\033[8m"

ESC_MY_MAGIC_ENDING = ESC_HIDDEN + ESC_NO_CHAR_ATTR

# not widely supported, use '22' instead
# ESC_RESET_BOLD       = "\033[21m"

ESC_RESET_DIM        = "\033[22m"
ESC_RESET_BOLD       = ESC_RESET_DIM

ESC_RESET_UNDERLINED = "\033[24m"
ESC_RESET_BLINK      = "\033[25m"
ESC_RESET_INVERTED   = "\033[27m"
ESC_RESET_HIDDEN     = "\033[28m"

ESC_DEFAULT       = "\033[39m"
ESC_BLACK         = "\033[30m"
ESC_RED           = "\033[31m"
ESC_GREEN         = "\033[32m"
ESC_YELLOW        = "\033[33m"
ESC_BLUE          = "\033[34m"
ESC_MAGENTA       = "\033[35m"
ESC_CYAN          = "\033[36m"
ESC_LIGHT_GREY    = "\033[37m"
ESC_DARK_GREY     = "\033[90m"
ESC_LIGHT_RED     = "\033[91m"
ESC_LIGHT_GREEN   = "\033[92m"
ESC_LIGHT_YELLOW  = "\033[93m"
ESC_LIGHT_BLUE    = "\033[94m"
ESC_LIGHT_MAGENTA = "\033[95m"
ESC_LIGHT_CYAN    = "\033[96m"
ESC_WHITE         = "\033[97m"

ESC_COLOR_TO_HTML = {
    ESC_BLACK         : '#000000',
    ESC_RED           : '#800000',
    ESC_GREEN         : '#008000',
    ESC_YELLOW        : '#808000',
    ESC_BLUE          : '#000080',
    ESC_MAGENTA       : '#800080',
    ESC_CYAN          : '#008080',
    ESC_LIGHT_GREY    : '#c0c0c0',
    ESC_DARK_GREY     : '#808080',
    ESC_LIGHT_RED     : '#ff0000',
    ESC_LIGHT_GREEN   : '#00ff00',
    ESC_LIGHT_YELLOW  : '#ffff00',
    ESC_LIGHT_BLUE    : '#0000ff',
    ESC_LIGHT_MAGENTA : '#ff00ff',
    ESC_LIGHT_CYAN    : '#00ffff',
    ESC_WHITE         : '#ffffff'}

ESC_SEQ_SET = [ESC_NO_CHAR_ATTR,
               ESC_BOLD,
               ESC_DIM,
               ESC_UNDERLINED,
               ESC_BLINK,
               ESC_INVERTED,
               ESC_HIDDEN,
               ESC_RESET_BOLD,
               ESC_RESET_DIM,
               ESC_RESET_UNDERLINED,
               ESC_RESET_BLINK,
               ESC_RESET_INVERTED,
               ESC_RESET_HIDDEN,
               ESC_DEFAULT,
               ESC_BLACK,
               ESC_RED,
               ESC_GREEN,
               ESC_YELLOW,
               ESC_BLUE,
               ESC_MAGENTA,
               ESC_CYAN,
               ESC_LIGHT_GREY,
               ESC_DARK_GREY,
               ESC_LIGHT_RED,
               ESC_LIGHT_GREEN,
               ESC_LIGHT_YELLOW,
               ESC_LIGHT_BLUE,
               ESC_LIGHT_MAGENTA,
               ESC_LIGHT_CYAN,
               ESC_WHITE]

# terminal reservation list, see terminal_reserve
TERMINAL_RESERVATION = {}
# these are classes that print progress bars, see terminal_reserve
TERMINAL_PRINT_LOOP_CLASSES = ["ProgressBar", "ProgressBarCounter", "ProgressBarFancy", "ProgressBarCounterFancy"]