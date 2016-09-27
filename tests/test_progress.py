#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function

import logging
import multiprocessing as mp
import numpy as np
import os
import psutil
import signal
import sys
import time
import traceback
import io

import warnings

warnings.filterwarnings('error')
warnings.filterwarnings('always', category=ImportWarning)


# setup path to import progress
from os.path import abspath, dirname, split
# Add parent directory to beginning of path variable
sys.path = [split(dirname(abspath(__file__)))[0]] + sys.path

import progress


# restore python2 compatibility
if sys.version_info[0] == 2:
    ProcessLookupError = OSError
    inMemoryBuffer = io.BytesIO
elif sys.version_info[0] == 3:
    inMemoryBuffer = io.StringIO

def _kill_pid(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, TypeError):
        pass

def _safe_assert_not_loop_is_alive(loop):
    try:
        assert not loop.is_alive()
    except AssertionError:
        _kill_pid(loop.getpid())
        raise

INTERVAL = 0.2
    
def test_prefix_logger():
    pl = logging.getLogger('new log')
    pl.setLevel(logging.DEBUG)
    pl.addHandler(progress.def_handl)

    time.sleep(0.1)
    
    pl.debug("{}this is an debug log{}".format(progress.ESC_BOLD, progress.ESC_NO_CHAR_ATTR))
    pl.info("this is an info %s log %s", 'a', 'b')
    pl.warning("this is an warning log")
    pl.error("this is an error log")
    pl.critical("this is an critical log")
    
    pl.debug("multiline\nline2\nline3")
    
    
    

def test_loop_basic():
    """
    run function f in loop
    
    check if it is alive after calling start()
    check if it is NOT alive after calling stop()
    """
    f = lambda: print("        I'm process {}".format(os.getpid()))
    try:
        loop = progress.Loop(func=f, interval=INTERVAL)
        loop.start()
        
        time.sleep(0.5*INTERVAL)
    
        assert loop.is_alive()
        print("[+] loop started")
        
        time.sleep(1.5*INTERVAL)
        loop.stop()
        
        _safe_assert_not_loop_is_alive(loop)  
        print("[+] loop stopped")
    finally:
        _kill_pid(loop.getpid())

def test_loop_signals():
    f = lambda: print("        I'm process {}".format(os.getpid()))
    try:
        loop = progress.Loop(func=f, interval=INTERVAL, sigint='stop', sigterm='stop')
        
        print("## stop on SIGINT ##")
        loop.start()
        time.sleep(0.5 * INTERVAL)
        loop.is_alive()
        
        pid = loop.getpid()
        print("    send SIGINT")
        os.kill(pid, signal.SIGINT)
        time.sleep(1.5 * INTERVAL)
        _safe_assert_not_loop_is_alive(loop)
        print("[+] loop stopped running")
    
        print("## stop on SIGTERM ##")    
        loop.start()
        time.sleep(0.5 * INTERVAL)
        pid = loop.getpid()
        print("    send SIGTERM")
        os.kill(pid, signal.SIGTERM)
        time.sleep(1.5 * INTERVAL)
        _safe_assert_not_loop_is_alive(loop)
        print("[+] loop stopped running")
        
        print("## ignore SIGINT ##")
        loop = progress.Loop(func=f, interval=INTERVAL, sigint='ign', sigterm='ign')
    
        loop.start()
        time.sleep(0.5*INTERVAL)
        pid = loop.getpid()
        os.kill(pid, signal.SIGINT)
        print("    send SIGINT")
        time.sleep(1.5*INTERVAL)
        assert loop.is_alive()
        print("[+] loop still running")
        print("    send SIGKILL")
        os.kill(pid, signal.SIGKILL)
        time.sleep(1.5*INTERVAL)
        assert not loop.is_alive()
        print("[+] loop stopped running")
        
        print("## ignore SIGTERM ##")
        loop.start()
        time.sleep(0.5*INTERVAL)
        pid = loop.getpid()
        print("    send SIGTERM")
        os.kill(pid, signal.SIGTERM)
        time.sleep(1.5*INTERVAL)
        assert loop.is_alive()
        print("[+] loop still running")
        print("    send SIGKILL")    
        os.kill(pid, signal.SIGKILL)
        time.sleep(1.5*INTERVAL)
        assert not loop.is_alive()
        print("[+] loop stopped running")
    finally:
        _kill_pid(loop.getpid())

def non_stopping_function():
    print("        I'm pid", os.getpid())
    print("        I'm NOT going to stop")
    
    while True:          # sleep will be interrupted by signal
        time.sleep(0.1)  # while True just calls sleep again
                         # only SIGKILL helps

def normal_function():
    print("        I'm pid", os.getpid())
    
def long_sleep_function():
    print("        I'm pid", os.getpid())
    print("        I will sleep for seven years")
    time.sleep(60*60*12*356*7)
    
def test_loop_normal_stop():
    try:
        with progress.Loop(func     = normal_function,
                           interval = INTERVAL) as loop:
            loop.start()
            time.sleep(0.5*INTERVAL)
            assert loop.is_alive()
            print("[+] normal loop running")
        
        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    finally:
        _kill_pid(loop.getpid())
            
def test_loop_stdout_pipe():
   
    myout = inMemoryBuffer()
    stdout = sys.stdout
    sys.stdout = myout
    
    test_string = "test out öäüß"
    
    try:
        with progress.Loop(func     = lambda: print(test_string),
                           interval = INTERVAL) as loop:
            loop.start()
            time.sleep(0.2*INTERVAL)
            assert loop.is_alive()        
        _safe_assert_not_loop_is_alive(loop)
    finally:
        sys.stdout = stdout
        _kill_pid(loop.getpid())
        
    cap_out = myout.getvalue()
    test_string = test_string+"\n"

    assert cap_out == test_string
            
def test_loop_pause():
   
    myout = inMemoryBuffer()
    stdout = sys.stdout
    sys.stdout = myout
    
    try:
        with progress.Loop(func     = normal_function,
                           interval = INTERVAL) as loop:
            loop.start()
            time.sleep(0.2*INTERVAL)
            assert loop.is_alive()
            print("[+] loop running")
            loop.pause()
            print("[+] loop paused")
            time.sleep(3*INTERVAL)
            loop.resume()
            print("[+] loop resumed")
            time.sleep(3*INTERVAL)
        
        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    finally:
        sys.stdout = stdout
        _kill_pid(loop.getpid())
            
    print(myout.getvalue())

           
def test_loop_logging():   
    my_err = io.StringIO()
    progress.def_handl.stream = my_err
                
    try:
        progress.log.setLevel(logging.ERROR)
        with progress.Loop(func          = normal_function,
                           interval      = INTERVAL) as loop:
            loop.start()
            time.sleep(0.5*INTERVAL)
            assert loop.is_alive()
            print("[+] normal loop running")
            loop.stop()
        
        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    finally:
        _kill_pid(loop.getpid())
        progress.log.setLevel(logging.DEBUG)
            
    s = my_err.getvalue()
    print(s)
    assert len(s) == 0 
    
    progress.def_handl.stream = sys.stderr
    
def test_loop_need_sigterm_to_stop():
    try:
        with progress.Loop(func    = long_sleep_function, 
                           interval = INTERVAL) as loop:
            loop.start()
            time.sleep(0.5*INTERVAL)
            assert loop.is_alive()
            print("[+] sleepy loop running")
            
        _safe_assert_not_loop_is_alive(loop)
        print("[+] sleepy loop stopped")
    finally:
        _kill_pid(loop.getpid())        
    
def test_loop_need_sigkill_to_stop():
    try:
        with progress.Loop(func                     = non_stopping_function, 
                           interval                 = INTERVAL,
                           auto_kill_on_last_resort = True) as loop:
            loop.start()
            time.sleep(0.5*INTERVAL)
            assert loop.is_alive()
            print("[+] NON stopping loop running")
    
        _safe_assert_not_loop_is_alive(loop)
        print("[+] NON stopping loop stopped")
    finally:
        _kill_pid(loop.getpid())        
        
def test_why_with_statement():
    """
        here we demonstrate why you should use the with statement
    """
    class ErrorLoop(progress.Loop):
        def raise_runtimeError(self):
            raise RuntimeError("on purpose error")
    v=2
    
    def t(shared_mem_pid):
        try:
            l = ErrorLoop(func=normal_function, interval=INTERVAL)
            l.start()
            time.sleep(1.5*INTERVAL)
            shared_mem_pid.value = l.getpid()
            l.raise_runtimeError()
            l.stop()
        finally:
            if l.getpid() is not None:
                os.kill(l.getpid(), signal.SIGKILL)            
        
    def t_with(shared_mem_pid):
        with ErrorLoop(func=normal_function, interval=INTERVAL) as l:
            try:
                l.start()
                time.sleep(1.5*INTERVAL)
                shared_mem_pid.value = l.getpid()
                l.raise_runtimeError()
                l.stop()
            finally:
                if l.getpid() is not None:
                    os.kill(l.getpid(), signal.SIGKILL)                
        
    print("## start without with statement ...")
    
    # the pid of the loop process, which is spawned inside 't'
    subproc_pid = progress.UnsignedIntValue()
    
    p = mp.Process(target=t, args=(subproc_pid, ))
    p.start()
    time.sleep(0.5*INTERVAL)
    print("## now an exception gets raised ... but you don't see it!")
    time.sleep(2*INTERVAL)
    print("## ... and the loop is still running so we have to kill the process")
    
    p.terminate()
    p.join(1)
    
    try:
        assert not p.is_alive()
        print("## ... done!")
        p_sub = psutil.Process(subproc_pid.value)
        if p_sub.is_running():
            print("## terminate loop process from extern ...")
            p_sub.terminate()
        
            p_sub.wait(1.5*INTERVAL)
            assert not p_sub.is_running()
            print("## process with PID {} terminated!".format(subproc_pid.value))
    except:
        pass
    else:
        if p_sub.is_running():
            os.kill(subproc_pid.value, signal.SIGKILL)        
    finally:
        if p.is_alive():
            os.kill(p.pid, signal.SIGKILL)

    
    time.sleep(INTERVAL)
    
    print("\n##\n## now to the same with the with statement ...")
    p = mp.Process(target=t_with, args=(subproc_pid, ))
    p.start()
    time.sleep(0.5*INTERVAL)
    print("## no special care must be taken ... cool eh!")   
    print("## ALL DONE! (there is no control when the exception from the loop get printed)")    
    p.join(1.5*INTERVAL)
    try:
        assert not p.is_alive()
    finally:
        if p.is_alive():
            # kill loop
            p_sub = psutil.Process(subproc_pid.value)
            if p_sub.is_running():
                os.kill(subproc_pid.value, signal.SIGKILL)    
            # kill sub process
            os.kill(p.pid, signal.SIGKILL)
    
    
def test_progress_bar():
    """
    deprecated, due to missing with
    """
    count = progress.UnsignedIntValue()
    max_count = progress.UnsignedIntValue(100)
    try:
        sb = progress.ProgressBar(count, max_count, interval = INTERVAL)
        assert not sb.is_alive()
        
        sb.start()
        time.sleep(1.5*INTERVAL)
        assert sb.is_alive()
        pid = sb.getpid()
        
        # call start on already running PB
        sb.start()
        time.sleep(INTERVAL)
        assert pid == sb.getpid()
        
        sb.stop()
        _safe_assert_not_loop_is_alive(sb)
        
        time.sleep(2*INTERVAL)
        # call stop on not running PB
        sb.stop()
        time.sleep(2*INTERVAL)
    finally:
        _kill_pid(sb.getpid())        
    
def test_progress_bar_with_statement():
    print("TERMINAL_RESERVATION", progress.TERMINAL_RESERVATION)
    count = progress.UnsignedIntValue()
    max_count = progress.UnsignedIntValue(100)
    try:
        with progress.ProgressBar(count, max_count, interval = INTERVAL) as sb:
            assert not sb.is_alive()
        
            sb.start()
            time.sleep(0.5*INTERVAL)
            assert sb.is_alive()
            pid = sb.getpid()
            
            # call start on already running PB
            sb.start()
            time.sleep(0.5*INTERVAL)
            assert pid == sb.getpid()
        
        _safe_assert_not_loop_is_alive(sb)
        
        time.sleep(0.5*INTERVAL)
        sb.stop()
    finally:
        _kill_pid(sb.getpid())           
    
def test_progress_bar_multi():
    print("TERMINAL_RESERVATION", progress.TERMINAL_RESERVATION)
    n = 4
    max_count_value = 100
    
    count = []
    max_count = []
    prepend = []
    for i in range(n):
        count.append(progress.UnsignedIntValue(0))
        max_count.append(progress.UnsignedIntValue(max_count_value))
        prepend.append('_{}_: '.format(i))
    try:
        with progress.ProgressBar(count=count,
                                  max_count=max_count,
                                  interval=INTERVAL,
                                  speed_calc_cycles=10,
                                  width='auto',
                                  sigint='stop',
                                  sigterm='stop',
                                  prepend=prepend) as sbm:
        
            sbm.start()
            
            for x in range(500):
                i = np.random.randint(low=0, high=n)
                with count[i].get_lock():
                    count[i].value += 1
                    
                if count[i].value > 100:
                    sbm.reset(i)
                    
                time.sleep(INTERVAL/50)
    finally:
        _kill_pid(sbm.getpid())
        
           
def test_status_counter():
    c = progress.UnsignedIntValue(val=0)
    m = None
    try:
        with progress.ProgressBar(count=c,
                                  max_count=m,
                                  interval=INTERVAL,
                                  speed_calc_cycles=100,
                                  sigint='ign',
                                  sigterm='ign',
                                  prepend='') as sc:
    
            sc.start()
            while True:
                with c.get_lock():
                    c.value += 1
                    
                if c.value == 100:
                    break
                
                time.sleep(INTERVAL/50)
    finally:
        _kill_pid(sc.getpid())
                  
            
def test_status_counter_multi():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    c = [c1, c2]
    prepend = ['c1: ', 'c2: ']
    try:
        with progress.ProgressBar(count=c, prepend=prepend, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    
                if c[0].value == 100:
                    break
                
                time.sleep(INTERVAL/50)
    finally:
        _kill_pid(sc.getpid())
                   
            
def test_intermediate_prints_while_running_progess_bar():
    c = progress.UnsignedIntValue(val=0)
    try:
        with progress.ProgressBar(count=c, interval=INTERVAL) as sc:
            sc.start()
            while True:
                with c.get_lock():
                    c.value += 1
                    
                if c.value == 25:
                    sc.stop()
                    print("intermediate message")
                    sc.start()
                    
                if c.value == 100:
                    break
                
                time.sleep(INTERVAL/50)    
    except:
        print("IN EXCEPTION TEST")
        traceback.print_exc()
    finally:
        _kill_pid(sc.getpid())
   
            
            
def test_intermediate_prints_while_running_progess_bar_multi():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    c = [c1,c2]
    try:
        with progress.ProgressBar(count=c, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    
                if c[0].value == 25:
                    sc.stop()
                    print("intermediate message")
                    sc.start()
                    
                if c[0].value == 100:
                    break
                
                time.sleep(INTERVAL/50)
    finally:
        _kill_pid(sc.getpid())
                   
    
def test_progress_bar_counter():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    maxc = 10
    m1 = progress.UnsignedIntValue(val=maxc)
    m2 = progress.UnsignedIntValue(val=maxc)
    
    c = [c1, c2]
    m = [m1, m2]
    
    t0 = time.time()
    
    pp = ['a ', 'b ']
    
    try:
        with progress.ProgressBarCounter(count=c, max_count=m, interval=INTERVAL, prepend = pp) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)
                               
                time.sleep(INTERVAL/50)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())
                   

def test_progress_bar_counter_non_max():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    c = [c1, c2]
    maxc = 10
    t0 = time.time()
    
    try:
        with progress.ProgressBarCounter(count=c, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)
                               
                time.sleep(INTERVAL/50)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())
                   
            
def test_progress_bar_counter_hide_bar():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    m1 = progress.UnsignedIntValue(val=0)
    
    c = [c1, c2]
    m = [m1, m1]
    maxc = 10
    t0 = time.time()
    
    try:
        with progress.ProgressBarCounter(count=c, max_count=m, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)
                               
                time.sleep(INTERVAL/50)
                if (time.time() - t0) > 2:
                    break       
    finally:
        _kill_pid(sc.getpid())
                   
            
def test_progress_bar_slow_change():   
    max_count_value = 5
    
    count = progress.UnsignedIntValue(0)
    max_count = progress.UnsignedIntValue(max_count_value)
    
    try:
        with progress.ProgressBar(count=count,
                                  max_count=max_count,
                                  interval=0.7,
                                  speed_calc_cycles=5) as sbm:
        
            sbm.start()
            for i in range(1, max_count_value+1):
                time.sleep(3)
                count.value = i
                                
    finally:
        _kill_pid(sbm.getpid())

    try:
        count.value = 0
        with progress.ProgressBarFancy(count=count,
                                  max_count=max_count,
                                  interval=0.7,
                                  speed_calc_cycles=15) as sbm:
        
            sbm.start()
            for i in range(1, max_count_value):
                time.sleep(3)
                count.value = i
                                
    finally:
        _kill_pid(sbm.getpid())
              
            
def test_progress_bar_start_stop():
    max_count_value = 20
    
    count = progress.UnsignedIntValue(0)
    max_count = progress.UnsignedIntValue(max_count_value)
    try:
        with progress.ProgressBar(count=count,
                                  max_count=max_count,
                                  interval=INTERVAL,
                                  speed_calc_cycles=5) as sbm:
        
            sbm.start()
            
            for i in range(max_count_value):
                time.sleep(INTERVAL/10)
                count.value = i+1
                if i == 10:
                    sbm.stop(make_sure_its_down = True)
                    print("this will not overwrite the progressbar, because we stopped it explicitly")
                    sbm.start()
            print("this WILL overwrite the progressbar, because we are still inside it's context (still running)")            
    finally:
        _kill_pid(sbm.getpid())
   

    print()
    print("create a progress bar, but do not start")
    try:
        with progress.ProgressBar(count=count,
                                  max_count=max_count,
                                  interval=INTERVAL,
                                  speed_calc_cycles=5) as sbm:
            pass
    finally:
        _kill_pid(sbm.getpid())
           
    print("this is after progress.__exit__, there should be no prints from the progress")
            
def test_progress_bar_fancy():
    count = progress.UnsignedIntValue()
    max_count = progress.UnsignedIntValue(100)
    try:
        with progress.ProgressBarFancy(count, max_count, interval=INTERVAL, width='auto') as sb:
            sb.start()
            for i in range(100):
                count.value = i+1
                time.sleep(INTERVAL/50)
    finally:
        _kill_pid(sb.getpid())                  
 
def test_progress_bar_multi_fancy():
    n = 4
    max_count_value = 25
    
    count = []
    max_count = []
    prepend = []
    for i in range(n):
        count.append(progress.UnsignedIntValue(0))
        max_count.append(progress.UnsignedIntValue(max_count_value))
        prepend.append('_{}_:'.format(i))
    try:
        with progress.ProgressBarFancy(count=count,
                                       max_count=max_count,
                                       interval=INTERVAL,
                                       speed_calc_cycles=10,
                                       width='auto',
                                       sigint='stop',
                                       sigterm='stop',
                                       prepend=prepend) as sbm:
        
            sbm.start()
            
            for x in range(400):
                i = np.random.randint(low=0, high=n)
                with count[i].get_lock():
                    count[i].value += 1
                    
                if count[i].value > 100:
                    sbm.reset(i)
                    
                time.sleep(INTERVAL/200)
    finally:
        _kill_pid(sbm.getpid())
                 
            
def test_progress_bar_fancy_small():
    count = progress.UnsignedIntValue()
    m = 15
    max_count = progress.UnsignedIntValue(m)
    
    for width in ['auto', 80,70,60,50,40,30,20,10,5]:
        try:    
            with progress.ProgressBarFancy(count, max_count, interval=INTERVAL, width=width) as sb:
                sb.start()
                for i in range(m):
                    count.value = i+1
                    time.sleep(INTERVAL/30)            
        finally:
            _kill_pid(sb.getpid())            
def test_progress_bar_counter_fancy():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    maxc = 30
    m1 = progress.UnsignedIntValue(val=maxc)
    m2 = progress.UnsignedIntValue(val=maxc)
    
    c = [c1, c2]
    m = [m1, m2]
    
    t0 = time.time()
    
    pp = ['a ', 'b ']
    try:
        with progress.ProgressBarCounterFancy(count=c, max_count=m, interval=INTERVAL, prepend = pp) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)
                               
                time.sleep(INTERVAL/60)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())                  

def test_progress_bar_counter_fancy_non_max():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    c = [c1, c2]
    maxc = 30
    t0 = time.time()
    try:
        with progress.ProgressBarCounterFancy(count=c, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)
                               
                time.sleep(INTERVAL/60)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())                  
            
def test_progress_bar_counter_fancy_hide_bar():
    c1 = progress.UnsignedIntValue(val=0)
    c2 = progress.UnsignedIntValue(val=0)
    
    m1 = progress.UnsignedIntValue(val=0)
    
    c = [c1, c2]
    m = [m1, m1]
    maxc = 30
    t0 = time.time()
    
    try:    
        with progress.ProgressBarCounterFancy(count=c, max_count=m, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0,2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)
                               
                time.sleep(INTERVAL/60)
                if (time.time() - t0) > 2:
                    break         
    finally:
        _kill_pid(sc.getpid())
                  

def test_info_line():
    c1 = progress.UnsignedIntValue(val=0)
    s  = progress.StringValue(80)
    m1 = progress.UnsignedIntValue(val=30)
    try:
        with progress.ProgressBarFancy(count=c1, max_count=m1, interval=INTERVAL, info_line=s) as sc:
            sc.start()
            while True:
                c1.value = c1.value + 1
                if c1.value > 10:
                    s.value = b'info_line\nline2' 
                time.sleep(INTERVAL/60)
                if c1.value >= m1.value:
                    break
    finally:
        _kill_pid(sc.getpid())
                   
            
def test_change_prepend():
    c1 = progress.UnsignedIntValue(val=0)
    m1 = progress.UnsignedIntValue(val=30)    
    try:
        with progress.ProgressBarFancy(count=c1, max_count=m1, interval=INTERVAL) as sc:
            sc.start()
            while True:
                c1.value = c1.value + 1
                sc.prepend = [str(c1.value)]
                time.sleep(INTERVAL/60)
                if c1.value >= m1.value:
                    break
    finally:
        _kill_pid(sc.getpid())
                   
            
def test_stop_progress_with_large_interval():
    c1 = progress.UnsignedIntValue(val=0)
    m1 = progress.UnsignedIntValue(val=10)    
    try:
        with progress.ProgressBarFancy(count=c1, max_count=m1, interval=10*INTERVAL) as sc:
            sc.start()
            while True:
                c1.value = c1.value + 1
                time.sleep(INTERVAL/5)
                if c1.value >= m1.value:
                    break
            print("done inner loop")
    finally:
        _kill_pid(sc.getpid())
               
    print("done progress")
    
def test_get_identifier():
    for bold in [True, False]:
        for name in [None, 'test']:
            for pid in [None, 'no PID']:
                id = progress.get_identifier(name=name, pid=pid, bold=bold)
                print(id)
    
def test_catch_subprocess_error():
    def f_error():
        raise RuntimeError("my ERROR")
    
    def f_no_error():
        print("no error")
        
    try:
        with progress.Loop(func     = f_no_error,
                           interval = INTERVAL) as loop:
            loop.start()
            time.sleep(0.5*INTERVAL)

        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    finally:
        _kill_pid(loop.getpid())

    try:
        with progress.Loop(func     = f_error,
                           interval = INTERVAL) as loop:
            loop.start()
            time.sleep(0.5*INTERVAL)

        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    except progress.LoopExceptionError:
        print("noticed that an exception occurred")
        
    finally:
        _kill_pid(loop.getpid())    
    
def test_stopping_loop():
    def f():
        return True
    
    try:
        with progress.Loop(func     = f,
                           interval = INTERVAL) as loop:
            loop.start()
            time.sleep(1.5*INTERVAL)
            
            print("this loop has stopped it self, because it returned True")
            _safe_assert_not_loop_is_alive(loop)
                   
    finally:
        _kill_pid(loop.getpid())

if __name__ == "__main__":
    func = [    
    test_catch_subprocess_error,
    test_prefix_logger,
    test_loop_basic,
    test_loop_signals,
    test_loop_logging,
    test_loop_normal_stop,
    test_loop_stdout_pipe,
    test_loop_pause,
    test_loop_need_sigterm_to_stop,
    test_loop_need_sigkill_to_stop,
    test_why_with_statement,
    test_progress_bar,
    test_progress_bar_with_statement,
    test_progress_bar_multi,
    test_status_counter,
    test_status_counter_multi,
    test_intermediate_prints_while_running_progess_bar,
    test_intermediate_prints_while_running_progess_bar_multi,
    test_progress_bar_counter,
    test_progress_bar_counter_non_max,
    test_progress_bar_counter_hide_bar,
    test_progress_bar_slow_change,
    test_progress_bar_start_stop,
    test_progress_bar_fancy,
    test_progress_bar_multi_fancy,
    test_progress_bar_fancy_small,
    test_progress_bar_counter_fancy,
    test_progress_bar_counter_fancy_non_max,
    test_progress_bar_counter_fancy_hide_bar,
    test_info_line,
    test_change_prepend,
    test_stop_progress_with_large_interval,
    test_get_identifier,
    test_stopping_loop,
    lambda: print("END")
    ]
    
    for f in func:
        print()
        print('#'*80)
        print('##  {}'.format(f.__name__))
        print()
        f()
        time.sleep(1)
    
