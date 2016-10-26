import multiprocessing as mp
import time
import signal
import os
import platform

def my_h(signal, frame):
    print("recieved signal", signal)
    raise InterruptedError

def a_task():
    signal.signal(signal.SIGINT, my_h)
    print("this is 'a_task'", os.getpid())
    try:
        while True:
            print(time.time())
            time.sleep(1)
    except Exception as e:
        print(type(e), e)
    print("'a_task' is at end")


if __name__ == '__main__':
    p = mp.Process(target=a_task)
    p.start()
    time.sleep(1)
    
    if platform.system() == 'Windows':
        print("send CTRL_C_EVENT")
        os.kill(p.pid, signal.CTRL_C_EVENT)
    elif platform.system() == 'Linux':
        print("send SIGINT")
        os.kill(p.pid, signal.SIGINT)

    time.sleep(3)
    try:
        os.kill(p.pid, signal.SIGTERM)
    except:
        pass


