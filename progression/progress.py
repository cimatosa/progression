#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function

import datetime
import io
import logging
import math
import multiprocessing as mp
from   multiprocessing.sharedctypes import Synchronized
import os
import sys
import signal
import subprocess as sp
import threading
import time
import traceback
import warnings

_IPYTHON = True
try:
    import ipywidgets
except:
    _IPYTHON = False
    warnings.warn("could not load ipywidgets (IPython HTML output will not work)", category=ImportWarning)
try:
    from IPython.display import display
except:
    _IPYTHON = False
    warnings.warn("could not load  IPython (IPython HTML output will not work)", category=ImportWarning)


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

if sys.version_info[0] == 2:         # minor hacks to be python 2 and 3 compatible
    ProcessLookupError = OSError
    inMemoryBuffer = io.BytesIO
elif sys.version_info[0] == 3:
    inMemoryBuffer = io.StringIO


class StdoutPipe(object):
    """replacement for stream objects such as stdout which
        forwards all incoming data using the send method of a
        connection

        example usage:

            >>> import sys
            >>> from multiprocessing import Pipe
            >>> from progression import StdoutPipe
            >>> conn_recv, conn_send = Pipe(False)
            >>> sys.stdout = StdoutPipe(conn_send)
            >>> print("hallo welt", end='')  # this is no going through the pipe
            >>> msg = conn_recv.recv()
            >>> sys.stdout = sys.__stdout__
            >>> print(msg)
            hallo welt
            >>> assert msg == "hallo welt"
    """
    def __init__(self, conn):
        self.conn = conn
        
    def flush(self):
        pass
    def write(self, b):
        self.conn.send(b)

class PipeToPrint(object):
    def __call__(self, b):
        print(b, end='')

class PipeFromProgressToIPythonHTMLWidget(object):
    def __init__(self):
        self.htmlWidget = ipywidgets.widgets.HTML()
        display(self.htmlWidget)
        self._buff = ""
    def __call__(self, b):
        self._buff += b
        if b.endswith(ESC_MY_MAGIC_ENDING):
            buff = ESC_SEQ_to_HTML(self._buff)
            self.htmlWidget.value = '<style>.widget-html{font-family:monospace;white-space:pre}</style>'+buff
            self._buff = ""

PipeHandler = PipeToPrint
def choose_pipe_handler(kind = 'print', color_theme = None):
    global PipeHandler
    if kind == 'print':
        PipeHandler = PipeToPrint
        if color_theme is None:
            choose_color_theme('term_default')
        else:
            choose_color_theme(color_theme)
    elif kind == 'ipythonhtml':
        if _IPYTHON:
            PipeHandler = PipeFromProgressToIPythonHTMLWidget
            if color_theme is None:
                choose_color_theme('ipyt_default')
            else:
                choose_color_theme(color_theme)
        else:
            warnings.warn("can not choose ipythonHTML (IPython and/or ipywidgets were not loaded)")

try:
    from shutil import get_terminal_size as shutil_get_terminal_size
except ImportError:
    shutil_get_terminal_size = None
    
if sys.version_info[0] == 2:
    old_math_ceil = math.ceil 
    def my_int_ceil(f):
        return int(old_math_ceil(f))
    
    math.ceil = my_int_ceil

# Magic conversion from 3 to 2
if sys.version_info[0] == 2:
    _jm_compatible_bytearray = lambda x: x
else:
    _jm_compatible_bytearray = bytearray

class LoopExceptionError(RuntimeError):
    pass

class LoopInterruptError(Exception):
    pass

def get_identifier(name=None, pid=None, bold=True):
    if pid is None:
        pid = os.getpid()

    if bold:
        esc_bold = ESC_BOLD
        esc_no_char_attr = ESC_NO_CHAR_ATTR
    else:
        esc_bold = ""
        esc_no_char_attr = ""

    if name is None:
        return "{}PID {}{}".format(esc_bold, pid, esc_no_char_attr)
    else:
        return "{}{} ({}){}".format(esc_bold, name, pid, esc_no_char_attr)    

class Loop(object):
    """
    class to run a function periodically an seperate process.
    
    In case the called function returns True, the loop will stop.
    Otherwise a time interval given by interval will be slept before
    another execution is triggered.
    
    The shared memory variable _run (accessible via the class property run)  
    also determines if the function if executed another time. If set to False
    the execution stops.
    
    For safe cleanup (and in order to catch any Errors)
    it is advisable to instantiate this class
    using 'with' statement as follows:
        
        with Loop(**kwargs) as my_loop:
            my_loop.start()
            ...
    
    this will guarantee you that the spawned loop process is
    down when exiting the 'with' scope.
    
    The only circumstance where the process is still running is
    when you set auto_kill_on_last_resort to False and answer the
    question to send SIGKILL with no.
    """
    def __init__(self, 
                 func, 
                 args                     = (),
                 interval                 = 1,
                 verbose                  = None,
                 sigint                   = 'stop',
                 sigterm                  = 'stop',
                 auto_kill_on_last_resort = False,
                 raise_error              = True):
        """
        func [callable] - function to be called periodically
        
        args [tuple] - arguments passed to func when calling
        
        intervall [pos number] - time to "sleep" between each call
        
        verbose - DEPRECATED, only kept for compatibility, use global log.level to 
        specify verbosity  
          
        sigint [string] - signal handler string to set SIGINT behavior (see below)
        
        sigterm [string] - signal handler string to set SIGTERM behavior (see below)
        
        auto_kill_on_last_resort [bool] - If set False (default), ask user to send SIGKILL 
        to loop process in case normal stop and SIGTERM failed. If set True, send SIDKILL
        without asking.
        
        the signal handler string may be one of the following
            ing: ignore the incoming signal
            stop: raise InterruptedError which is caught silently.
        """
        self._proc = None
        
        if verbose is not None:
            log.warning("verbose is deprecated, only allowed for compatibility")
            warnings.warn("verbose is deprecated", DeprecationWarning)        
            
        self.func = func
        self.args = args
        self.interval = interval
        assert self.interval >= 0
        self._run   = mp.Value('b', False)
        self._pause = mp.Value('b', False)
        
        self._sigint = sigint
        self._sigterm = sigterm
        
        self._auto_kill_on_last_resort = auto_kill_on_last_resort
        log.debug("auto_kill_on_last_resort = %s", self._auto_kill_on_last_resort)
        
        self._monitor_thread = None
        self.pipe_handler = PipeHandler()
        self.raise_error = raise_error

    def __enter__(self):
        return self
    
    def __exit__(self, *exc_args):       
        if self.is_alive():
            log.debug("loop is still running on context exit")
        else:    
            log.debug("loop has stopped on context exit")
        self.stop()
        

    def __cleanup(self):
        """
        Wait at most twice as long as the given repetition interval
        for the _wrapper_function to terminate.
        
        If after that time the _wrapper_function has not terminated,
        send SIGTERM to and the process.
        
        Wait at most five times as long as the given repetition interval
        for the _wrapper_function to terminate.
        
        If the process still running send SIGKILL automatically if
        auto_kill_on_last_resort was set True or ask the
        user to confirm sending SIGKILL
        """
        # set run to False and wait some time -> see what happens            
        self.run = False
        if check_process_termination(proc                     = self._proc,
                                     timeout                  = 2*self.interval,
                                     prefix                   = '',
                                     auto_kill_on_last_resort = self._auto_kill_on_last_resort):
            log.debug("cleanup successful")
        else:
            raise RuntimeError("cleanup FAILED!")
        try:
            self.conn_send.close()
        except OSError:
            pass
        log.debug("wait for monitor thread to join")
        self._monitor_thread.join()      

    @staticmethod
    def _wrapper_func(func, args, shared_mem_run, shared_mem_pause, interval, log_queue, sigint, sigterm, name, logging_level, conn_send):
        """
            to be executed as a separate process (that's why this functions is declared static)
        """
        prefix = get_identifier(name)+' '
        global log
        log = logging.getLogger(__name__+'.'+"log_{}".format(get_identifier(name, bold=False)))
        log.setLevel(logging_level)

        # try:
        #     log.addHandler(QueueHandler(log_queue))
        # except NameError:
        #     log.addHandler(def_handl)
            
        sys.stdout = StdoutPipe(conn_send)
                  
        log.debug("enter wrapper_func")            

        SIG_handler_Loop(sigint, sigterm, log, prefix)

        while shared_mem_run.value:
            try:
                # in pause mode, simply sleep 
                if shared_mem_pause.value:
                    quit_loop = False
                else:
                    # if not pause mode -> call func and see what happens
                    try:
                        quit_loop = func(*args)
                    except LoopInterruptError:
                        raise
                    except Exception as e:
                        log.error("error %s occurred in loop alling 'func(*args)'", type(e))
                        log.info("show traceback.print_exc()\n%s", traceback.format_exc())
                        sys.exit(-1)
    
                    if quit_loop is True:
                        log.debug("loop stooped because func returned True")
                        break
                    
                time.sleep(interval)
            except LoopInterruptError:
                log.debug("quit wrapper_func due to InterruptedError")
                break

        log.debug("wrapper_func terminates gracefully")
        
    def _monitor_stdout_pipe(self):
        while True:
            try:
                b = self.conn_recv.recv()
                self.pipe_handler(b)
            except EOFError:
                break


        
    def start(self):
        """
        uses multiprocess Process to call _wrapper_func in subprocess 
        """

        if self.is_alive():
            log.warning("a process with pid %s is already running", self._proc.pid)
            return
            
        self.run = True

        # try:
        #     log_queue = mp.Queue(-1)
        #     listener = QueueListener(log_queue, def_handl)
        #     listener.start()
        # except NameError:
        #     log.error("QueueListener not available in this python version (need at least 3.2)\n"
        #               "this may resault in incoheerent logging")
        #     log_queue = None
        log_queue = None
        name = self.__class__.__name__
        
        self.conn_recv, self.conn_send = mp.Pipe(False)
        self._monitor_thread = threading.Thread(target = self._monitor_stdout_pipe)
        self._monitor_thread.daemon=True
        self._monitor_thread.start()
        log.debug("started monitor thread")
        
        self._proc = mp.Process(target = Loop._wrapper_func, 
                                args   = (self.func, self.args, self._run, self._pause, self.interval, 
                                          log_queue, self._sigint, self._sigterm, name, log.level, self.conn_send))
        self._proc.start()
        log.debug("started a new process with pid %s", self._proc.pid)
        
    def stop(self):
        """
        stops the process triggered by start
        
        Setting the shared memory boolean run to false, which should prevent
        the loop from repeating. Call __cleanup to make sure the process
        stopped. After that we could trigger start() again.
        """
        if self.is_alive():
            self._proc.terminate()
            
        if self._proc is not None:
            self.__cleanup()
                   
            if self.raise_error:
                if self._proc.exitcode == 255:
                    raise LoopExceptionError("the loop function return non zero exticode!\n"+
                                             "see log (INFO level) for traceback information") 
        
        self._proc = None
        
    def join(self, timeout):
        """
        calls join for the spawned process with given timeout
        """
        if self.is_alive():
            self._proc.join(timeout)
    
    def is_alive(self):
        if self._proc is None:
            return False
        else:
            return self._proc.is_alive()
        
    def pause(self):
        if self.run:
            self._pause.value = True
            log.debug("process with pid %s paused", self._proc.pid)
        
    def resume(self):
        if self.run:
            self._pause.value = False
            log.debug("process with pid %s resumed", self._proc.pid)

    def getpid(self):
        if self._proc is not None:
            return self._proc.pid
        else:
            return None
    
    @property
    def run(self):
        """
        makes the shared memory boolean accessible as class attribute
        
        Set run False, the loop will stop repeating.
        Calling start, will set run True and start the loop again as a new process.
        """
        return self._run.value
    @run.setter
    def run(self, run):
        self._run.value = run



class Progress(Loop):
    """
    Abstract Progress Loop
    
    Uses Loop class to implement a repeating function to display the progress
    of multiples processes.
    
    In the simplest case, given only a list of shared memory values 'count' (NOTE: 
    a single value will be automatically mapped to a one element list),
    the total elapses time (TET) and a speed estimation are calculated for
    each process and passed to the display function show_stat.
    
    This functions needs to be implemented in a subclass. It is intended to show
    the progress of ONE process in one line.
    
    When max_count is given (in general as list of shared memory values, a single
    shared memory value will be mapped to a one element list) the time to go TTG
    will also be calculated and passed tow show_stat.
    
    Information about the terminal width will be retrieved when setting width='auto'.
    If supported by the terminal emulator the width in characters of the terminal
    emulator will be stored in width and also passed to show_stat. 
    Otherwise, a default width of 80 characters will be chosen.
    
    Also you can specify a fixed width by setting width to the desired number.
    
    NOTE: in order to achieve multiline progress special escape sequences are used
    which may not be supported by all terminal emulators.
    
    example:

        c1 = UnsignedIntValue(val=0)
        c2 = UnsignedIntValue(val=0)
    
        c = [c1, c2]
        prepend = ['c1: ', 'c2: ']
        with ProgressCounter(count=c, prepend=prepend) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    
                if c[0].value == 1000:
                    break
                
                time.sleep(0.01)
    
    using start() within the 'with' statement ensures that the subprocess
    which is started by start() in order to show the progress repeatedly
    will be terminated on context exit. Otherwise one has to make sure
    that at some point the stop() routine is called. When dealing with 
    signal handling and exception this might become tricky, so that the  
    use of the 'with' statement is highly encouraged. 
    """    
    def __init__(self, 
                 count, 
                 max_count         = None,
                 prepend           = None,
                 width             = 'auto',
                 speed_calc_cycles = 10, 
                 interval          = 1, 
                 verbose           = None,
                 sigint            = 'stop', 
                 sigterm           = 'stop',
                 info_line         = None):
        """       
        count [mp.Value] - shared memory to hold the current state, (list or single value)
        
        max_count [mp.Value] - shared memory holding the final state, (None, list or single value),
        may be changed by external process without having to explicitly tell this class.
        If None, no TTG and relative progress can be calculated -> TTG = None 
        
        prepend [string] - string to put in front of the progress output, (None, single string
        or of list of strings)
        
        interval [int] - seconds to wait between progress print
        
        speed_calc_cycles [int] - use the current (time, count) as
        well as the (old_time, old_count) read by the show_stat function 
        speed_calc_cycles calls before to calculate the speed as follows:
        s = count - old_count / (time - old_time)
        
        verbose, sigint, sigterm -> see loop class  
        """
        
        if verbose is not None:
            log.warning("verbose is deprecated, only allowed for compatibility")
            warnings.warn("verbose is deprecated", DeprecationWarning)        

        try:
            for c in count:
                if not isinstance(c, Synchronized):
                    raise ValueError("Each element of 'count' must be if the type multiprocessing.sharedctypes.Synchronized")
            self.is_multi = True
        except TypeError:
            if not isinstance(count, Synchronized):
                raise ValueError("'count' must be if the type multiprocessing.sharedctypes.Synchronized")
            self.is_multi = False
            count = [count]
        
        self.len = len(count)
            
        if max_count is not None:
            if self.is_multi:
                try:
                    for i, m in enumerate(max_count):
                        if not isinstance(m, Synchronized):
                            max_count[i] = UnsignedIntValue(m)
                except TypeError:
                    raise TypeError("'max_count' must be iterable")
            else:
                if not isinstance(max_count, Synchronized):
                    max_count = UnsignedIntValue(max_count)
                max_count = [max_count]
        else:
            max_count = [None] * self.len
        
        self.start_time = []
        self.speed_calc_cycles = speed_calc_cycles
        
        self.width = width
        
        self.q = []
        self.prepend = []
        self.lock = []
        self.last_count = []
        self.last_speed = []
        for i in range(self.len):
            self.q.append(myQueue())  # queue to save the last speed_calc_cycles
                                      # (time, count) information to calculate speed
            self.last_count.append(UnsignedIntValue())
            self.last_speed.append(FloatValue())
            self.lock.append(mp.Lock())
            self.start_time.append(FloatValue(val=time.time()))
            if prepend is None:
                # no prepend given
                self.prepend.append('')
            else:
                if isinstance(prepend, str):
                    self.prepend.append(prepend)
                else:
                    # assume list of prepend, (needs to be a sequence)
                    self.prepend.append(prepend[i])

        self.max_count = max_count  # list of multiprocessing value type
        self.count = count          # list of multiprocessing value type
        
        self.interval = interval
        self.verbose = verbose

        self.show_on_exit = False
        self.add_args = {}
        
        self.info_line = info_line
        
        # setup loop class with func
        Loop.__init__(self,
                      func = Progress.show_stat_wrapper_multi,

                      args = (self.count,
                              self.last_count,
                              self.start_time,
                              self.max_count,
                              self.speed_calc_cycles,
                              self.width,
                              self.q,
                              self.last_speed,
                              self.prepend,
                              self.__class__.show_stat,
                              self.len,
                              self.add_args,
                              self.lock,
                              self.info_line),
                      interval = interval,
                      sigint   = sigint,
                      sigterm  = sigterm,
                      auto_kill_on_last_resort = True)

    def __exit__(self, *exc_args):
        self.stop()
            
        
    @staticmethod
    def _calc(count, 
              last_count, 
              start_time, 
              max_count, 
              speed_calc_cycles, 
              q, 
              last_speed,
              lock):
        """
            do the pre calculations in order to get TET, speed, TTG
            and call the actual display routine show_stat with these arguments
            
            NOTE: show_stat is purely abstract and need to be reimplemented to
            achieve a specific progress display.  
        """
        count_value = count.value
        start_time_value = start_time.value
        current_time = time.time()
        
        if last_count.value != count_value:
            # some progress happened
        
            with lock:
                # save current state (count, time) to queue
                
                q.put((count_value, current_time))
    
                # get older state from queue (or initial state)
                # to to speed estimation                
                if q.qsize() > speed_calc_cycles:
                    old_count_value, old_time = q.get()
                else:
                    old_count_value, old_time = 0, start_time_value
            
            last_count.value = count_value
            #last_old_count.value = old_count_value
            #last_old_time.value = old_time
            
            speed = (count_value - old_count_value) / (current_time - old_time)
            last_speed.value = speed 
        else:
            # progress has not changed since last call
            # use also old (cached) data from the queue
            #old_count_value, old_time = last_old_count.value, last_old_time.value
            speed = last_speed.value  

        if (max_count is None):
            max_count_value = None
        else:
            max_count_value = max_count.value
            
        tet = (current_time - start_time_value)
        
        if (speed == 0) or (max_count_value is None) or (max_count_value == 0):
            ttg = None
        else:
            ttg = math.ceil((max_count_value - count_value) / speed)
            
        return count_value, max_count_value, speed, tet, ttg

    def _reset_all(self):
        """
            reset all progress information
        """
        for i in range(self.len):
            self._reset_i(i)

    def _reset_i(self, i):
        """
            reset i-th progress information
        """
        self.count[i].value=0
        log.debug("reset counter %s", i)
        self.lock[i].acquire()
        for x in range(self.q[i].qsize()):
            self.q[i].get()
        
        self.lock[i].release()
        self.start_time[i].value = time.time()

    def _show_stat(self):
        """
            convenient functions to call the static show_stat_wrapper_multi with
            the given class members
        """
        Progress.show_stat_wrapper_multi(self.count,
                                         self.last_count, 
                                         self.start_time, 
                                         self.max_count, 
                                         self.speed_calc_cycles,
                                         self.width,
                                         self.q,
                                         self.last_speed,
                                         self.prepend,
                                         self.__class__.show_stat,
                                         self.len, 
                                         self.add_args,
                                         self.lock,
                                         self.info_line,
                                         no_move_up=True)

    def reset(self, i = None):
        """
            convenient function to reset progress information
            
            i [None, int] - None: reset all, int: reset process indexed by i 
        """
#        super(Progress, self).stop()
        if i is None:
            self._reset_all()
        else:
            self._reset_i(i)
#        super(Progress, self).start()

    @staticmethod        
    def show_stat(count_value, max_count_value, prepend, speed, tet, ttg, width, **kwargs):
        """
            re implement this function in a subclass
            
            count_value - current value of progress
            
            max_count_value - maximum value the progress can take
            
            prepend - some extra string to be put for example in front of the
            progress display
            
            speed - estimated speed in counts per second (use for example humanize_speed
            to get readable information in string format)
            
            tet - total elapsed time in seconds (use for example humanize_time
            to get readable information in string format)
            
            ttg - time to go in seconds (use for example humanize_time
            to get readable information in string format)
        """
        raise NotImplementedError

    @staticmethod        
    def show_stat_wrapper(count, 
                          last_count, 
                          start_time, 
                          max_count, 
                          speed_calc_cycles, 
                          width, 
                          q,
                          last_speed,
                          prepend, 
                          show_stat_function,
                          add_args, 
                          i, 
                          lock):
        count_value, max_count_value, speed, tet, ttg, = Progress._calc(count, 
                                                                        last_count, 
                                                                        start_time, 
                                                                        max_count, 
                                                                        speed_calc_cycles, 
                                                                        q,
                                                                        last_speed, 
                                                                        lock) 
        return show_stat_function(count_value, max_count_value, prepend, speed, tet, ttg, width, i, **add_args)

    @staticmethod
    def show_stat_wrapper_multi(count, 
                                last_count, 
                                start_time, 
                                max_count, 
                                speed_calc_cycles, 
                                width, 
                                q, 
                                last_speed,
                                prepend, 
                                show_stat_function, 
                                len_, 
                                add_args,
                                lock,
                                info_line,
                                no_move_up=False):
        """
            call the static method show_stat_wrapper for each process
        """
#         print(ESC_BOLD, end='')
#         sys.stdout.flush()
        for i in range(len_):
            Progress.show_stat_wrapper(count[i], 
                                       last_count[i], 
                                       start_time[i], 
                                       max_count[i], 
                                       speed_calc_cycles, 
                                       width, 
                                       q[i],
                                       last_speed[i],
                                       prepend[i], 
                                       show_stat_function, 
                                       add_args, 
                                       i, 
                                       lock[i])
        n = len_
        if info_line is not None:
            s = info_line.value.decode('utf-8')
            s = s.split('\n')
            n += len(s)
            for si in s:
                if width == 'auto':
                    width = get_terminal_width()
                if len(si) > width:
                    si = si[:width]
                print("{0:<{1}}".format(si, width))
        
        if no_move_up:
            n = 0
                                    # this is only a hack to find the end
                                    # of the message in a stream
                                    # so ESC_HIDDEN+ESC_NO_CHAR_ATTR is a magic ending
        print(ESC_MOVE_LINE_UP(n) + ESC_MY_MAGIC_ENDING, end='')
        sys.stdout.flush()

    def start(self):
        # before printing any output to stout, we can now check this
        # variable to see if any other ProgressBar has reserved that
        # terminal.
        
        if (self.__class__.__name__ in TERMINAL_PRINT_LOOP_CLASSES):
            if not terminal_reserve(progress_obj=self):
                log.warning("tty already reserved, NOT starting the progress loop!")
                return
        
        super(Progress, self).start()
        self.show_on_exit = True

    def stop(self):
        """
            trigger clean up by hand, needs to be done when not using
            context management via 'with' statement
        
            - will terminate loop process
            - show a last progress -> see the full 100% on exit
            - releases terminal reservation
        """
        super(Progress, self).stop()
        terminal_unreserve(progress_obj=self, verbose=self.verbose)

        if self.show_on_exit:
            if not isinstance(self.pipe_handler, PipeToPrint):
                myout = inMemoryBuffer()
                stdout = sys.stdout
                sys.stdout = myout
                self._show_stat()
                self.pipe_handler(myout.getvalue())
                sys.stdout = stdout
            else:
                self._show_stat()
                print()
        self.show_on_exit = False
        

class ProgressBar(Progress):
    """
    implements a progress bar similar to the one known from 'wget' or 'pv'
    """
    def __init__(self, *args, **kwargs):
        """
            width [int/'auto'] - the number of characters used to show the Progress bar,
            use 'auto' to determine width from terminal information -> see _set_width
        """
        Progress.__init__(self, *args, **kwargs)

        self._PRE_PREPEND = ESC_NO_CHAR_ATTR + ESC_RED
        self._POST_PREPEND = ESC_BOLD + ESC_GREEN

    @staticmethod        
    def show_stat(count_value, max_count_value, prepend, speed, tet, ttg, width, i, **kwargs):
        if (max_count_value is None) or (max_count_value == 0):
            # only show current absolute progress as number and estimated speed
            print("{}{}{} [{}] {}#{}    ".format(ESC_NO_CHAR_ATTR,
                                                 COLTHM['PRE_COL'] + prepend + ESC_DEFAULT,
                                                 humanize_time(tet), humanize_speed(speed),
                                                 ESC_BOLD + COLTHM['BAR_COL'],
                                                 count_value))
        else:
            if width == 'auto':
                width = get_terminal_width()
            
            # deduce relative progress and show as bar on screen
            if ttg is None:
                s3 = " TTG --"
            else:
                s3 = " TTG {}".format(humanize_time(ttg))
               
            s1 = "{}{}{} [{}] ".format(ESC_NO_CHAR_ATTR,
                                      COLTHM['PRE_COL'] + prepend + ESC_DEFAULT,
                                      humanize_time(tet),
                                      humanize_speed(speed))
            
            l = len_string_without_ESC(s1+s3)
            l2 = width - l - 3
            a = int(l2 * count_value / max_count_value)
            b = l2 - a
            s2 = COLTHM['BAR_COL'] + ESC_BOLD + "[" + "="*a + ">" + " "*b + "]" + ESC_RESET_BOLD + ESC_DEFAULT

            print(s1+s2+s3)


class ProgressBarCounter(Progress):
    """
        records also the time of each reset and calculates the speed
        of the resets.
        
        shows the TET since init (not effected by reset)
        the speed of the resets (number of finished processed per time)
        and the number of finished processes
        
        after that also show a progress of each process
        max_count > 0 and not None -> bar
        max_count == None -> absolute count statistic
        max_count == 0 -> hide process statistic at all 
    """
    def __init__(self, speed_calc_cycles_counter=5, **kwargs):       
        Progress.__init__(self, **kwargs)
        
        self.counter_count = []
        self.counter_q = []
        self.counter_speed = []
        for i in range(self.len):
            self.counter_count.append(UnsignedIntValue(val=0))
            self.counter_q.append(myQueue())
            self.counter_speed.append(FloatValue())
        
        self.counter_speed_calc_cycles = speed_calc_cycles_counter
        self.init_time = time.time()
            
        self.add_args['counter_count'] = self.counter_count
        self.add_args['counter_speed'] = self.counter_speed
        self.add_args['init_time'] = self.init_time

    def get_counter_count(self, i=0):
        return self.counter_count[i].value
        
    def _reset_i(self, i):
        c = self.counter_count[i] 
        with c.get_lock():
            c.value += 1
            
        count_value = c.value
        q = self.counter_q[i]
         
        current_time = time.time()
        q.put((count_value, current_time))
        
        if q.qsize() > self.counter_speed_calc_cycles:
            old_count_value, old_time = q.get()
        else:
            old_count_value, old_time = 0, self.init_time

        speed = (count_value - old_count_value) / (current_time - old_time)
        
        self.counter_speed[i].value = speed
                    
        Progress._reset_i(self, i)
        
    @staticmethod
    def show_stat(count_value, max_count_value, prepend, speed, tet, ttg, width, i, **kwargs):
        counter_count = kwargs['counter_count'][i]
        counter_speed = kwargs['counter_speed'][i]
        counter_tet = time.time() - kwargs['init_time']
        
        s_c = "{}{}{} [{}] {}#{} - ".format(ESC_NO_CHAR_ATTR,
                                            COLTHM['PRE_COL']+prepend+ESC_DEFAULT,
                                            humanize_time(counter_tet),
                                            humanize_speed(counter_speed.value),
                                            COLTHM['BAR_COL'],
                                            str(counter_count.value) + ESC_DEFAULT)

        if width == 'auto':
            width = get_terminal_width()
        
        if (max_count_value is None) or (max_count_value == 0):
            s_c = "{}{} [{}] {}#{}    ".format(s_c,
                                               humanize_time(tet),
                                               humanize_speed(speed),
                                               COLTHM['BAR_COL'],
                                               str(count_value)+ ESC_DEFAULT)
        else:
            if ttg is None:
                s3 = " TTG --"
            else:
                s3 = " TTG {}".format(humanize_time(ttg))

            s1 = "{} [{}] ".format(humanize_time(tet), humanize_speed(speed))

            l = len_string_without_ESC(s1 + s3 + s_c)
            l2 = width - l - 3

            a = int(l2 * count_value / max_count_value)
            b = l2 - a
            s2 = COLTHM['BAR_COL'] + ESC_BOLD + "[" + "=" * a + ">" + " " * b + "]" + ESC_RESET_BOLD + ESC_DEFAULT
            s_c = s_c+s1+s2+s3

        print(s_c)

class ProgressBarFancy(Progress):
    """
        implements a progress bar where the color indicates the current status
        similar to the bars known from 'htop'
    """
    def __init__(self, *args, **kwargs):
        """
            width [int/'auto'] - the number of characters used to show the Progress bar,
            use 'auto' to determine width from terminal information -> see _set_width
        """            
        Progress.__init__(self, *args, **kwargs)
        
    @staticmethod        
    def get_d(s1, s2, width, lp, lps):
        d = width-len(remove_ESC_SEQ_from_string(s1))-len(remove_ESC_SEQ_from_string(s2))-2-lp-lps
        if d >= 0:
            d1 = d // 2
            d2 = d - d1
            return s1, s2, d1, d2

    @staticmethod
    def full_stat(p, tet, speed, ttg, eta, ort, repl_ch, width, lp, lps):
        s1 = "TET {} {:>12} TTG {}".format(tet, speed, ttg)
        s2 = "ETA {} ORT {}".format(eta, ort)
        return ProgressBarFancy.get_d(s1, s2, width, lp, lps)


    @staticmethod
    def full_minor_stat(p, tet, speed, ttg, eta, ort, repl_ch, width, lp, lps):
        s1 = "E {} {:>12} G {}".format(tet, speed, ttg)
        s2 = "A {} O {}".format(eta, ort)
        return ProgressBarFancy.get_d(s1, s2, width, lp, lps)

    @staticmethod
    def reduced_1_stat(p, tet, speed, ttg, eta, ort, repl_ch, width, lp, lps):
        s1 = "E {} {:>12} G {}".format(tet, speed, ttg)
        s2 = "O {}".format(ort)
        return ProgressBarFancy.get_d(s1, s2, width, lp, lps)  

    @staticmethod
    def reduced_2_stat(p, tet, speed, ttg, eta, ort, repl_ch, width, lp, lps):
        s1 = "E {} G {}".format(tet, ttg)
        s2 = "O {}".format(ort)
        return ProgressBarFancy.get_d(s1, s2, width, lp, lps)
    
    @staticmethod
    def reduced_3_stat(p, tet, speed, ttg, eta, ort, repl_ch, width, lp, lps):
        s1 = "E {} G {}".format(tet, ttg)
        s2 = ''
        return ProgressBarFancy.get_d(s1, s2, width, lp, lps)
    
    @staticmethod
    def reduced_4_stat(p, tet, speed, ttg, eta, ort, repl_ch, width, lp, lps):
        s1 = ''
        s2 = ''
        return ProgressBarFancy.get_d(s1, s2, width, lp, lps)    

    @staticmethod        
    def kw_bold(s, ch_after):
        kws = ['TET', 'TTG', 'ETA', 'ORT', 'E', 'G', 'A', 'O']
        for kw in kws:
            for c in ch_after:
                s = s.replace(kw + c, ESC_BOLD + kw + ESC_RESET_BOLD + c)
            
        return s

    @staticmethod        
    def _stat(count_value, max_count_value, prepend, speed, tet, ttg, width, i, **kwargs):
        if (max_count_value is None) or (max_count_value == 0):
            # only show current absolute progress as number and estimated speed
            stat = "{}{} [{}] {}#{}    ".format(COLTHM['PRE_COL']+prepend+ESC_DEFAULT,
                                                humanize_time(tet),
                                                humanize_speed(speed),
                                                COLTHM['BAR_COL'],
                                                str(count_value) + ESC_DEFAULT)
        else:
            if width == 'auto':
                width = get_terminal_width()
            # deduce relative progress
            p = count_value / max_count_value
            if p < 1:
                ps = " {:.1%} ".format(p)
            else:
                ps = " {:.0%} ".format(p)
            
            if ttg is None:
                eta = '--'
                ort = None
            else:
                eta = datetime.datetime.fromtimestamp(time.time() + ttg).strftime("%Y%m%d_%H:%M:%S")
                ort = tet + ttg
                
            tet = humanize_time(tet)
            speed = '['+humanize_speed(speed)+']'
            ttg = humanize_time(ttg)
            ort = humanize_time(ort)
            repl_ch = '-'
            lp = len(prepend)
            
            args = p, tet, speed, ttg, eta, ort, repl_ch, width, lp, len(ps)
            
            res = ProgressBarFancy.full_stat(*args)
            if res is None:
                res = ProgressBarFancy.full_minor_stat(*args)
                if res is None:
                    res = ProgressBarFancy.reduced_1_stat(*args)
                    if res is None:
                        res = ProgressBarFancy.reduced_2_stat(*args)
                        if res is None:
                            res = ProgressBarFancy.reduced_3_stat(*args)
                            if res is None:
                                res = ProgressBarFancy.reduced_4_stat(*args)
                                    
            if res is not None:
                s1, s2, d1, d2 = res                
                s = s1 + ' '*d1 + ps + ' '*d2 + s2
                s_before = s[:math.ceil(width*p)].replace(' ', repl_ch)
                if (len(s_before) > 0) and (s_before[-1] == repl_ch):
                    s_before = s_before[:-1] + '>'
                s_after  = s[math.ceil(width*p):]
                
                s_before = ProgressBarFancy.kw_bold(s_before, ch_after=[repl_ch, '>'])
                s_after = ProgressBarFancy.kw_bold(s_after, ch_after=[' '])
                stat = (COLTHM['PRE_COL']+prepend+ESC_DEFAULT+
                        COLTHM['BAR_COL']+ESC_BOLD + '[' + ESC_RESET_BOLD + s_before + ESC_DEFAULT +
                        s_after + ESC_BOLD + COLTHM['BAR_COL']+']' + ESC_NO_CHAR_ATTR)
            else:
                ps = ps.strip()
                if p == 1:
                    ps = ' '+ps
                stat = prepend + ps

        return stat

    @staticmethod        
    def show_stat(count_value, max_count_value, prepend, speed, tet, ttg, width, i, **kwargs):
        stat = ProgressBarFancy._stat(count_value, max_count_value, prepend, speed, tet, ttg, width, i, **kwargs)
        print(stat)

class ProgressBarCounterFancy(ProgressBarCounter):
    @staticmethod
    def show_stat(count_value, max_count_value, prepend, speed, tet, ttg, width, i, **kwargs):
        counter_count = kwargs['counter_count'][i]
        counter_speed = kwargs['counter_speed'][i]
        counter_tet = time.time() - kwargs['init_time']

        s_c = "{}{}{} [{}] {}#{} - ".format(ESC_NO_CHAR_ATTR,
                                            COLTHM['PRE_COL']+prepend+ESC_DEFAULT,
                                            humanize_time(counter_tet),
                                            humanize_speed(counter_speed.value),
                                            COLTHM['BAR_COL'],
                                            str(counter_count.value) + ESC_DEFAULT)

        if width == 'auto':
            width = get_terminal_width()        

        if (max_count_value is None) or (max_count_value == 0):
            s_c = "{}{} [{}] {}#{}    ".format(s_c, humanize_time(tet), humanize_speed(speed),
                                               COLTHM['BAR_COL'], str(count_value)+ESC_DEFAULT)
        else:
            _width = width - len_string_without_ESC(s_c)
            s_c += ProgressBarFancy._stat(count_value, max_count_value, '', speed, tet, ttg, _width, i)

        print(s_c)
                        

class SIG_handler_Loop(object):
    """class to setup signal handling for the Loop class
    
    Note: each subprocess receives the default signal handling from it's parent.
    If the signal function from the module signal is evoked within the subprocess
    this default behavior can be overwritten.
    
    The init function receives a shared memory boolean object which will be set
    false in case of signal detection. Since the Loop class will check the state 
    of this boolean object before each repetition, the loop will stop when
    a signal was receives.
    """
    def __init__(self, sigint, sigterm, log, prefix):
        self.set_signal(signal.SIGINT, sigint)
        self.set_signal(signal.SIGTERM, sigterm)
        self.prefix = prefix
        self.log = log
        self.log.info("setup signal handler for loop (SIGINT:%s, SIGTERM:%s)", sigint, sigterm)

    def set_signal(self, sig, handler_str):
        if handler_str == 'ign':
            signal.signal(sig, self._ignore_signal)
        elif handler_str == 'stop':
            signal.signal(sig, self._stop_on_signal)
        else:
            raise TypeError("unknown signal hander string '%s'", handler_str)
    
    def _ignore_signal(self, signal, frame):
        pass

    def _stop_on_signal(self, signal, frame):
        self.log.info("received sig %s -> raise InterruptedError", signal_dict[signal])
        raise LoopInterruptError()

def FloatValue(val=0.):
    return mp.Value('d', val, lock=True)

def UnsignedIntValue(val=0):
    return mp.Value('I', val, lock=True)

def StringValue(num_of_bytes):
    return mp.Array('c', _jm_compatible_bytearray(num_of_bytes), lock=True)

def check_process_termination(proc, prefix, timeout, auto_kill_on_last_resort = False):
    proc.join(timeout)
    if not proc.is_alive():
        log.debug("termination of process (pid %s) within timeout of %ss SUCCEEDED!", proc.pid, timeout)
        return True
        
    # process still runs -> send SIGTERM -> see what happens
    log.warning("termination of process (pid %s) within given timeout of %ss FAILED!", proc.pid, timeout)
 
    proc.terminate()
    new_timeout = 3*timeout
    log.debug("wait for termination (timeout %s)", new_timeout)
    proc.join(new_timeout)
    if not proc.is_alive():
        log.info("termination of process (pid %s) via SIGTERM with timeout of %ss SUCCEEDED!", proc.pid, new_timeout)
        return True
        
    
    log.warning("termination of process (pid %s) via SIGTERM with timeout of %ss FAILED!", proc.pid, new_timeout)

    log.debug("auto_kill_on_last_resort is %s", auto_kill_on_last_resort)
    answer = 'k' if auto_kill_on_last_resort else '_'
    while True:
        log.debug("answer string is %s", answer)
        if answer == 'k':
            log.warning("send SIGKILL to process with pid %s", proc.pid)
            os.kill(proc.pid, signal.SIGKILL)
            time.sleep(0.1)
        else:
            log.info("send SIGTERM to process with pid %s", proc.pid)
            os.kill(proc.pid, signal.SIGTERM)
            time.sleep(0.1)
            
        if not proc.is_alive():
            log.info("process (pid %s) has stopped running!", proc.pid)
            return True
        else:
            log.warning("process (pid %s) is still running!", proc.pid)

        print("the process (pid %s) seems still running".format(proc.pid))
        try:
            answer = input("press 'enter' to send SIGTERM, enter 'k' to send SIGKILL or enter 'ignore' to not bother about the process anymore")
        except Exception as e:
            log.error("could not ask for sending SIGKILL due to {}".format(type(e)))
            log.info(traceback.format_exc())
            log.warning("send SIGKILL now")
            answer = 'k'

        if answer == 'ignore':
            log.warning("ignore process %s", proc.pid)
            return False
        elif answer != 'k':
            answer = ''

def getCountKwargs(func):
    """ Returns a list ["count kwarg", "count_max kwarg"] for a
    given function. Valid combinations are defined in 
    `progress.validCountKwargs`.
    
    Returns None if no keyword arguments are found.
    """
    # Get all arguments of the function
    if hasattr(func, "__code__"):
        func_args = func.__code__.co_varnames[:func.__code__.co_argcount]
        for pair in validCountKwargs:
            if ( pair[0] in func_args and pair[1] in func_args ):
                return pair
    # else
    return None


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


def humanize_speed(c_per_sec):
    """convert a speed in counts per second to counts per [s, min, h, d], choosing the smallest value greater zero.
    """
    scales = [60, 60, 24]
    units = ['c/s', 'c/min', 'c/h', 'c/d']
    speed = c_per_sec
    i = 0
    if speed > 0:
        while (speed < 1) and (i < len(scales)):
            speed *= scales[i]
            i += 1
        
    return "{:.1f}{}".format(speed, units[i])


def humanize_time(secs):
    """convert second in to hh:mm:ss format
    """
    if secs is None:
        return '--'

    if secs < 1:
        return "{:.2f}ms".format(secs*1000)
    elif secs < 10:
        return "{:.2f}s".format(secs)
    else:
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return '{:02d}:{:02d}:{:02d}'.format(int(hours), int(mins), int(secs))
    


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

    
    if terminal_obj in TERMINAL_RESERVATION:    # terminal was already registered
        log.debug("this terminal %s has already been added to reservation list", terminal_obj)
        
        if TERMINAL_RESERVATION[terminal_obj] is progress_obj:
            log.debug("we %s have already reserved this terminal %s", progress_obj, terminal_obj)
            return True
        else:
            log.debug("someone else %s has already reserved this terminal %s", TERMINAL_RESERVATION[terminal_obj], terminal_obj)
            return False
    else:                                       # terminal not yet registered
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
        terminal_obj =sys.stdout

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
            log.debug("you %s can NOT unreserve terminal %s be cause it was reserved by %s", progress_obj, terminal_obj, po)
            
def codecov_subprocess_check():
    print("this line will be only called from a subprocess")


myQueue = mp.Queue

# a mapping from the numeric values of the signals to their names used in the
# standard python module signals
signal_dict = {}
for s in dir(signal):
    if s.startswith('SIG') and s[3] != '_':
        n = getattr(signal, s)
        if n in signal_dict:
            signal_dict[n] += ('/'+s)
        else:
            signal_dict[n] = s

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

_colthm_term_default = {'PRE_COL': ESC_RED, 'BAR_COL': ESC_LIGHT_GREEN}
_colthm_ipyt_default = {'PRE_COL': ESC_RED, 'BAR_COL': ESC_LIGHT_BLUE}

color_themes = {'term_default': _colthm_term_default,
                'ipyt_default': _colthm_ipyt_default}

COLTHM = _colthm_term_default
def choose_color_theme(name):
    global COLTHM
    if name in color_themes:
        COLTHM = color_themes[name]
    else:
        warnings.warn("no such color theme {}".format(name))


# terminal reservation list, see terminal_reserve
TERMINAL_RESERVATION = {}
# these are classes that print progress bars, see terminal_reserve
TERMINAL_PRINT_LOOP_CLASSES = ["ProgressBar", "ProgressBarCounter", "ProgressBarFancy", "ProgressBarCounterFancy"]

# keyword arguments that define counting in wrapped functions
validCountKwargs = [
                    [ "count", "count_max"],
                    [ "count", "max_count"],
                    [ "c", "m"],
                    [ "jmc", "jmm"],
                   ]
