import multiprocessing as mp
import time
import signal
import os
import platform
import threading
import _thread
import sys


def interrupt_handler(interrupt_event):
    print("before wait")
    interrupt_event.wait()
    print("after wait")
    _thread.interrupt_main()


def a_task(interrupt_event, *args):
    task = threading.Thread(target=interrupt_handler, args=(interrupt_event,))
    task.start()

    print("this is 'a_task'", os.getpid())
    try:
        while True:
            print(time.time())
            time.sleep(1)
    except KeyboardInterrupt:
        print("got KeyboardInterrupt")
    print("'a_task' is at end")


if __name__ == "__main__":
    interrupt_event = mp.Event()
    p = mp.Process(target=a_task, args=(interrupt_event, tuple()))
    p.start()
    time.sleep(2)
    print("set interrupt_event")
    interrupt_event.set()

    time.sleep(3)
    try:
        os.kill(p.pid, signal.SIGTERM)
    except:
        pass
