import sys
import multiprocessing as mp
import time
import signal
import os
import psutil
import ctypes

def my_h(signal, frame):
    print("recieved signal", signal)
    raise InterruptedError

def a_task():
    for i in [x for x in dir(signal) if x.startswith('SIG')]:
        try:
            signum = getattr(signal, i)
            signal.signal(signum, my_h)
            print("setup handler for", i)
        except ValueError:
            print("skip", i)

    print("this is 'a_task'", os.getpid())
    try:
        i = 0
        while True:
            print(i)
            i += 1
            time.sleep(0.8)
            os.kill(os.getpid(), signal.CTRL_C_EVENT)
    except Exception as e:
        print(type(e), e)
    print("'a_task' is at end")

def ignsig(s, f):
    print("ignore", s)

if __name__ == '__main__':
    p = mp.Process(target=a_task)
    p.start()
    time.sleep(1)
    for i in [x for x in dir(signal) if x.startswith('SIG')]:
        try:
            signum = getattr(signal, i)
            signal.signal(signum, ignsig)
            print("setup handler for", i)
        except ValueError:
            print("skip", i)
    time.sleep(2)
    print(os.getpid())
    print(p.pid)
    print("send signal")

    pid = os.getpid()

    #os.kill(p.pid, signal.CTRL_BREAK_EVENT)
    #os.kill(os.getpid(), signal.CTRL_BREAK_EVENT)
    r = ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, pid)
    print(r)
    #pp = psutil.Process(pid=p.pid)
    #pp.send_signal(sig = signal.CTRL_BREAK_EVENT)

    #ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, p.pid)

    print("signal sent")
    time.sleep(3)
    os.kill(p.pid, signal.SIGTERM)


