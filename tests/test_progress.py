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

warnings.filterwarnings("error")
warnings.filterwarnings("ignore", category=ImportWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

import progression


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
LOOP_START_TIMEOUT = 1

def_handl = logging.StreamHandler(
    stream=sys.stderr
)  # the default handler simply uses stderr
def_handl.setLevel(logging.DEBUG)  # ... listens to all messaged


def test_prefix_logger():
    pl = logging.getLogger("new log")
    pl.setLevel(logging.DEBUG)
    pl.addHandler(def_handl)

    time.sleep(0.1)

    pl.debug(
        "{}this is a debug log{}".format(
            progression.terminal.ESC_BOLD, progression.terminal.ESC_NO_CHAR_ATTR
        )
    )
    pl.info("this is an info %s log %s", "a", "b")
    pl.warning("this is a warning log")
    pl.error("this is an error log")
    pl.critical("this is a critical log")

    pl.debug("multiline\nline2\nline3")


def f_print_pid():
    print("        I'm process {}".format(os.getpid()))


def test_loop_basic():
    """
    run function f in loop

    check if it is alive after calling start()
    check if it is NOT alive after calling stop()
    """
    try:
        loop = progression.Loop(func=f_print_pid, interval=INTERVAL)
        loop.start(LOOP_START_TIMEOUT)
        assert loop.is_running()
        print("[+] loop started")

        time.sleep(0.5 * INTERVAL)
        loop.stop()
        assert not loop.is_running()
        assert not loop.is_alive()
        print("[+] loop stopped")
    finally:
        _kill_pid(loop.getpid())


def test_loop_start_stop():
    """
    start a loop
    stop a loop
    start the same instance again
    stop that instance
    """
    try:
        loop = progression.Loop(func=f_print_pid, interval=INTERVAL)
        print("\nstart")
        loop.start(LOOP_START_TIMEOUT)
        assert loop.is_running()
        time.sleep(0.5 * INTERVAL)
        print("\nstop")
        loop.stop()
        assert not loop.is_running()
        assert not loop.is_alive()

        time.sleep(INTERVAL)
        print("\nstart")
        loop.start(LOOP_START_TIMEOUT)
        assert loop.is_running()
        print("\nstop")
        loop.stop()
        assert not loop.is_running()
        assert not loop.is_alive()
    finally:
        _kill_pid(loop.getpid())


def test_loop_start_timeout():
    """
    catch the LoopTimeoutException that occurs when
    it takes tool long to fork/spawn the subprocess
    """
    try:
        loop = progression.Loop(
            func=f_print_pid, interval=INTERVAL, sigint="stop", sigterm="stop"
        )
        loop.start(timeout=0)
    except progression.LoopTimeoutError as e:
        print("caught {} ({})".format(type(e), e))
    finally:
        _kill_pid(loop.getpid())


def test_loop_signals():
    """
    test the signaling behavior

    usually SIGINT and SIGTERM lead to normal stop

    when set to 'ign', this signals will be ignored,
    causing the loop to continue running

    only SIGKILL helps now which does not allow the function to do any cleanup
    """
    try:
        loop = progression.Loop(
            func=f_print_pid, interval=INTERVAL, sigint="stop", sigterm="stop"
        )

        print("## stop on SIGINT ##")
        loop.start(LOOP_START_TIMEOUT)
        assert loop.is_running()
        time.sleep(0.5 * INTERVAL)
        pid = loop.getpid()
        os.kill(pid, signal.SIGINT)
        time.sleep(1.5 * INTERVAL)
        assert not loop.is_running()
        assert not loop.is_alive()
        print("[+] loop stopped running")

        time.sleep(INTERVAL)
        print("## stop on SIGTERM ##")
        loop.start(LOOP_START_TIMEOUT)
        assert loop.is_running()
        pid = loop.getpid()
        print("    send SIGTERM")
        os.kill(pid, signal.SIGTERM)
        time.sleep(1.5 * INTERVAL)
        assert not loop.is_running()
        assert not loop.is_alive()
        print("[+] loop stopped running")

        time.sleep(INTERVAL)
        print("## ignore SIGINT ##")
        loop = progression.Loop(
            func=f_print_pid, interval=INTERVAL, sigint="ign", sigterm="ign"
        )
        loop.start(LOOP_START_TIMEOUT)
        assert loop.is_running()
        pid = loop.getpid()
        os.kill(pid, signal.SIGINT)
        print("    send SIGINT")
        time.sleep(1.5 * INTERVAL)
        assert loop.is_alive()
        assert loop.is_running()
        print("[+] loop still running")
        print("    send SIGKILL")
        os.kill(pid, signal.SIGKILL)
        time.sleep(1.5 * INTERVAL)
        assert not loop.is_running()
        assert not loop.is_alive()
        print("[+] loop stopped running")

        time.sleep(INTERVAL)
        print("## ignore SIGTERM ##")
        loop.start(LOOP_START_TIMEOUT)
        assert loop.is_running()
        pid = loop.getpid()
        print("    send SIGTERM")
        os.kill(pid, signal.SIGTERM)
        time.sleep(1.5 * INTERVAL)
        assert loop.is_alive()
        assert loop.is_running()
        print("[+] loop still running")
        print("    send SIGKILL")
        os.kill(pid, signal.SIGKILL)
        time.sleep(1.5 * INTERVAL)
        assert not loop.is_running()
        assert not loop.is_alive()
        print("[+] loop stopped running")
    finally:
        _kill_pid(loop.getpid())


def non_stopping_function():
    """
    this function
    """
    print("        I'm pid", os.getpid())
    print("        I will ignore the InterruptedError")

    while True:
        try:
            time.sleep(0.1)
        except progression.LoopInterruptError:
            print("        I told you ;-)")


def normal_function():
    print("        I'm pid", os.getpid())


def long_sleep_function():
    print("        I'm pid", os.getpid())
    print("        I will sleep for seven years")
    time.sleep(60 * 60 * 12 * 356 * 7)


def test_loop_normal_stop():
    """
    simply reaching the end of the context stops the subprocess
    because it is nicely responding (short execution time)

    not really a difference to test_loop_need_sigterm_to_stop
    because SIGTERM is send right away to allows quicker close
    """
    try:
        with progression.Loop(func=normal_function, interval=INTERVAL) as loop:
            loop.start(LOOP_START_TIMEOUT)
            assert loop.is_running()
            print("[+] normal loop running")

        assert not loop.is_alive()
        print("[+] normal loop stopped")
    finally:
        _kill_pid(loop.getpid())


def test_loop_need_sigterm_to_stop():
    """
    the function called will sleep 7 years
    but a SIGTERM( which is translated to InterruptedError)
    will stop that function
    """
    try:
        with progression.Loop(func=long_sleep_function, interval=INTERVAL) as loop:
            loop.start()
            assert loop.is_running()
            print("[+] sleepy loop running")

        assert not loop.is_alive()
        print("[+] sleepy loop stopped")
    finally:
        _kill_pid(loop.getpid())


def test_loop_need_sigkill_to_stop():
    """
    as the function called ignores InterruptedError the
    normal shutdown mechanism fails,
    SIGKILL will be send automatically as last line of defense
    """
    try:
        with progression.Loop(
            func=non_stopping_function, interval=INTERVAL, auto_kill_on_last_resort=True
        ) as loop:
            loop.start()
            assert loop.is_running()
            print("[+] NON stopping loop running")

        assert not loop.is_alive()
        print("[+] NON stopping loop stopped")
    finally:
        _kill_pid(loop.getpid())


TEST_STR = "test out öäüß"


def print_test_str():
    print(TEST_STR)


def test_loop_stdout_pipe():
    """
    check the output of the loop function to stdout

    it is internally piped to the stdout of the parent process (this process)
    so if this stdout is redirected to a buffer we can check the output
    """

    myout = io.StringIO()
    stdout = sys.stdout
    sys.stdout = myout

    try:
        with progression.Loop(func=print_test_str, interval=INTERVAL) as loop:
            loop.start(LOOP_START_TIMEOUT)
            assert loop.is_running()
        assert not loop.is_alive()
    finally:
        sys.stdout = stdout
        _kill_pid(loop.getpid())

    cap_out = myout.getvalue()
    test_string = TEST_STR + "\n"
    assert cap_out == test_string


def test_loop_pause():
    """
    test loop pause behavior
    which simply skipped to call the function
    but keeps the wrapper_fuction alive
    """
    try:
        with progression.Loop(func=normal_function, interval=INTERVAL) as loop:
            loop.start(LOOP_START_TIMEOUT)
            assert loop.is_running()
            print("[+] loop running")
            loop.pause()
            print("[+] loop paused")
            time.sleep(2 * INTERVAL)
            assert loop.is_running()

            loop.resume()
            print("[+] loop resumed")
            time.sleep(2 * INTERVAL)

        assert not loop.is_alive()
        print("[+] normal loop stopped")
    finally:
        _kill_pid(loop.getpid())


def test_loop_logging():
    my_err = io.StringIO()
    stream_hdl = logging.StreamHandler(my_err)
    stream_hdl.setFormatter(progression.fmt)
    progression.log.addHandler(stream_hdl)

    ll = progression.log.level
    progression.log.level = logging.INFO

    time.sleep(0.5 * INTERVAL)

    try:
        with progression.Loop(func=normal_function, interval=INTERVAL) as loop:
            loop.start()
            pid = loop.getpid()
            time.sleep(0.5 * INTERVAL)
            assert loop.is_alive()
            print("[+] normal loop running")
            loop.stop()

        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    finally:
        _kill_pid(loop.getpid())
        progression.log.setLevel(ll)

    s = my_err.getvalue()
    print(s)
    assert (
        "progression.progress INFO : started a new process with pid {}".format(pid) in s
    )
    assert (
        "progression.progress.log_Loop_{} INFO : received sig SIGTERM -> raise InterruptedError".format(
            pid
        )
        in s
    )

    progression.log.removeHandler(stream_hdl)
    progression.log.level = ll


def loop_without_WITH(shared_mem_pid):
    l = progression.Loop(func=normal_function, interval=INTERVAL)
    l.start(LOOP_START_TIMEOUT)

    # this is needed so we can kill the loop from the outside
    shared_mem_pid.value = l.getpid()
    raise RuntimeError("on purpose error")

    # this will never be called
    l.stop()


def loop_with_WITH(shared_mem_pid):
    with progression.Loop(func=normal_function, interval=INTERVAL) as l:
        l.start(LOOP_START_TIMEOUT)

        # this is needed so we can kill the loop from the outside
        shared_mem_pid.value = l.getpid()
        raise RuntimeError("on purpose error")

        # this will never be called ... but the context manager does
        l.stop()


def test_loop_why_with_statement():
    """
    if an error occurs in the loop class
    or anywhere before stop() is called
    this error is not shown and the loops stop()
    function will never be called
    """
    print("## start without with statement ...")

    # the pid of the loop process, which is spawned inside 't'
    subproc_pid = progression.UnsignedIntValue()

    p = mp.Process(target=loop_without_WITH, args=(subproc_pid,))
    p.start()
    time.sleep(2 * INTERVAL)
    print("## now an exception gets raised ... but you don't see it!")
    time.sleep(2 * INTERVAL)
    print("## ... and the loop is still running")

    print("## Terminate the process which runs the loop ...")
    p.terminate()
    p.join(1)

    try:
        assert not p.is_alive()
        print("## done!")
        p_sub = psutil.Process(subproc_pid.value)
        if p_sub.is_running():
            print("## Nonetheless the subprocess from the Loop class still runs")
            print("## Terminate loop process from extern ...")
            p_sub.terminate()

            p_sub.wait(1.5 * INTERVAL)
            assert not p_sub.is_running()
            print("## process with PID {} terminated!".format(subproc_pid.value))
        else:
            assert False
    finally:
        _kill_pid(subproc_pid.value)
        _kill_pid(p.pid)

    print("\n##\n## now to the same with the with statement ...")
    p = mp.Process(target=loop_with_WITH, args=(subproc_pid,))
    p.start()
    time.sleep(0.5 * INTERVAL)
    print("## no special care must be taken ... cool eh!")
    print(
        "## ALL DONE! (there is no control when the exception from the loop get printed)"
    )
    p.join(1.5 * INTERVAL)
    try:
        assert not p.is_alive()
        assert not psutil.pid_exists(subproc_pid.value)

    finally:
        _kill_pid(subproc_pid.value)
        _kill_pid(p.pid)


def f_error():
    print("      I'm pid", os.getpid())
    print("      I raise an assertion now")
    assert False


_f_error_later_c = 5


def f_error_later():
    global _f_error_later_c
    print("      I'm pid", os.getpid(), "c =", _f_error_later_c)
    _f_error_later_c -= 1
    if _f_error_later_c == 0:
        assert False


def test_loop_with_error_in_func():
    try:
        with progression.Loop(func=f_error, interval=INTERVAL) as l:
            l.start(LOOP_START_TIMEOUT)
            time.sleep(0.5 * INTERVAL)
    except progression.LoopExceptionError as e:
        print("caught {} ({})".format(type(e), e))

    try:
        with progression.Loop(func=f_error_later, interval=INTERVAL) as l:
            l.start(LOOP_START_TIMEOUT)
            time.sleep(6 * INTERVAL)
    except progression.LoopExceptionError as e:
        print("caught {} ({})".format(type(e), e))


def test_progress_bar_with_statement():
    count = progression.UnsignedIntValue()
    max_count = progression.UnsignedIntValue(100)
    try:
        with progression.ProgressBar(count, max_count, interval=INTERVAL) as sb:
            assert not sb.is_alive()
            sb.start()
            assert sb.is_running()
            pid = sb.getpid()

            # call start on already running PB
            sb.start()
            time.sleep(0.5 * INTERVAL)
            assert pid == sb.getpid()

        assert not sb.is_alive()

        time.sleep(0.5 * INTERVAL)
        sb.stop()
    finally:
        _kill_pid(sb.getpid())


def test_progress_bar_multi():
    n = 4
    max_count_value = 100

    count = []
    max_count = []
    prepend = []
    for i in range(n):
        count.append(progression.UnsignedIntValue(0))
        max_count.append(progression.UnsignedIntValue(max_count_value))
        prepend.append("_{}_: ".format(i))
    try:
        with progression.ProgressBar(
            count=count,
            max_count=max_count,
            interval=INTERVAL,
            speed_calc_cycles=10,
            width="auto",
            sigint="stop",
            sigterm="stop",
            prepend=prepend,
        ) as sbm:

            sbm.start()
            for x in range(500):
                i = np.random.randint(low=0, high=n)
                with count[i].get_lock():
                    count[i].value += 1

                if count[i].value > 100:
                    sbm.reset(i)

                time.sleep(INTERVAL / 50)
    finally:
        _kill_pid(sbm.getpid())


def test_status_counter():
    c = progression.UnsignedIntValue(val=0)
    m = None
    try:
        with progression.ProgressBar(
            count=c,
            max_count=m,
            interval=INTERVAL,
            speed_calc_cycles=100,
            sigint="ign",
            sigterm="ign",
            prepend="",
        ) as sc:

            sc.start()
            while True:
                with c.get_lock():
                    c.value += 1

                if c.value == 100:
                    break

                time.sleep(INTERVAL / 50)
    finally:
        _kill_pid(sc.getpid())


def test_status_counter_multi():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    c = [c1, c2]
    prepend = ["c1: ", "c2: "]
    try:
        with progression.ProgressBar(count=c, prepend=prepend, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1

                if c[0].value == 100:
                    break

                time.sleep(INTERVAL / 50)
    finally:
        _kill_pid(sc.getpid())


def test_intermediate_prints_while_running_progess_bar():
    c = progression.UnsignedIntValue(val=0)
    try:
        with progression.ProgressBar(count=c, interval=INTERVAL) as sc:
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

                time.sleep(INTERVAL / 50)
    except:
        print("IN EXCEPTION TEST")
        traceback.print_exc()
    finally:
        _kill_pid(sc.getpid())


def test_intermediate_prints_while_running_progess_bar_multi():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    c = [c1, c2]
    try:
        with progression.ProgressBar(count=c, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1

                if c[0].value == 25:
                    sc.stop()
                    print("intermediate message")
                    sc.start()

                if c[0].value == 100:
                    break

                time.sleep(INTERVAL / 50)
    finally:
        _kill_pid(sc.getpid())


def test_progress_bar_counter():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    maxc = 10
    m1 = progression.UnsignedIntValue(val=maxc)
    m2 = progression.UnsignedIntValue(val=maxc)

    c = [c1, c2]
    m = [m1, m2]

    t0 = time.time()

    pp = ["a ", "b "]

    try:
        with progression.ProgressBarCounter(
            count=c, max_count=m, interval=INTERVAL, prepend=pp
        ) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)

                time.sleep(INTERVAL / 50)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_progress_bar_counter_non_max():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    c = [c1, c2]
    maxc = 10
    t0 = time.time()

    try:
        with progression.ProgressBarCounter(count=c, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)

                time.sleep(INTERVAL / 50)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_progress_bar_counter_hide_bar():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    m1 = progression.UnsignedIntValue(val=0)

    c = [c1, c2]
    m = [m1, m1]
    maxc = 10
    t0 = time.time()

    try:
        with progression.ProgressBarCounter(
            count=c, max_count=m, interval=INTERVAL
        ) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)

                time.sleep(INTERVAL / 50)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_progress_bar_slow_change():
    max_count_value = 3

    count = progression.UnsignedIntValue(0)
    max_count = progression.UnsignedIntValue(max_count_value)

    try:
        with progression.ProgressBar(
            count=count, max_count=max_count, interval=0.2, speed_calc_cycles=5
        ) as sbm:

            sbm.start()
            for i in range(1, max_count_value + 1):
                time.sleep(1)
                count.value = i

    finally:
        _kill_pid(sbm.getpid())

    try:
        count.value = 0
        with progression.ProgressBarFancy(
            count=count, max_count=max_count, interval=0.7, speed_calc_cycles=15
        ) as sbm:

            sbm.start()
            for i in range(1, max_count_value):
                time.sleep(3)
                count.value = i

    finally:
        _kill_pid(sbm.getpid())


def test_progress_bar_start_stop():
    max_count_value = 20

    count = progression.UnsignedIntValue(0)
    max_count = progression.UnsignedIntValue(max_count_value)
    try:
        with progression.ProgressBar(
            count=count, max_count=max_count, interval=INTERVAL, speed_calc_cycles=5
        ) as sbm:

            sbm.start()

            for i in range(max_count_value):
                time.sleep(INTERVAL / 10)
                count.value = i + 1
                if i == 10:
                    sbm.stop()
                    print(
                        "this will not overwrite the progressbar, because we stopped it explicitly"
                    )
                    sbm.start()
            print(
                "this WILL overwrite the progressbar, because we are still inside it's context (still running)"
            )
    finally:
        _kill_pid(sbm.getpid())

    print()
    print("create a progression bar, but do not start")
    try:
        with progression.ProgressBar(
            count=count, max_count=max_count, interval=INTERVAL, speed_calc_cycles=5
        ) as sbm:
            pass
    finally:
        _kill_pid(sbm.getpid())

    print(
        "this is after progression.__exit__, there should be no prints from the progression"
    )


def test_progress_bar_fancy():
    count = progression.UnsignedIntValue()
    max_count = progression.UnsignedIntValue(100)
    try:
        with progression.ProgressBarFancy(
            count, max_count, interval=INTERVAL, width="auto"
        ) as sb:
            sb.start()
            for i in range(100):
                count.value = i + 1
                time.sleep(INTERVAL / 50)
    finally:
        _kill_pid(sb.getpid())


def test_progress_bar_multi_fancy():
    n = 4
    max_count_value = 25

    count = []
    max_count = []
    prepend = []
    for i in range(n):
        count.append(progression.UnsignedIntValue(0))
        max_count.append(progression.UnsignedIntValue(max_count_value))
        prepend.append("_{}_:".format(i))
    try:
        with progression.ProgressBarFancy(
            count=count,
            max_count=max_count,
            interval=INTERVAL,
            speed_calc_cycles=10,
            width="auto",
            sigint="stop",
            sigterm="stop",
            prepend=prepend,
        ) as sbm:

            sbm.start()

            for x in range(400):
                i = np.random.randint(low=0, high=n)
                with count[i].get_lock():
                    count[i].value += 1

                if count[i].value > max_count[i].value:
                    sbm.reset(i)

                time.sleep(INTERVAL / 200)
    finally:
        _kill_pid(sbm.getpid())


def test_progress_bar_fancy_small():
    count = progression.UnsignedIntValue()
    m = 15
    max_count = progression.UnsignedIntValue(m)

    for width in ["auto", 80, 70, 60, 50, 40, 30, 20, 10, 5]:
        try:
            with progression.ProgressBarFancy(
                count, max_count, interval=INTERVAL, width=width
            ) as sb:
                sb.start()
                for i in range(m):
                    count.value = i + 1
                    time.sleep(INTERVAL / 30)
        finally:
            _kill_pid(sb.getpid())


def test_progress_bar_counter_fancy():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    maxc = 30
    m1 = progression.UnsignedIntValue(val=maxc)
    m2 = progression.UnsignedIntValue(val=maxc)

    c = [c1, c2]
    m = [m1, m2]

    t0 = time.time()

    pp = ["a ", "b "]
    try:
        with progression.ProgressBarCounterFancy(
            count=c, max_count=m, interval=INTERVAL, prepend=pp
        ) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)

                time.sleep(INTERVAL / 60)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_progress_bar_counter_fancy_non_max():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    c = [c1, c2]
    maxc = 30
    t0 = time.time()
    try:
        with progression.ProgressBarCounterFancy(count=c, interval=INTERVAL) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)

                time.sleep(INTERVAL / 60)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_progress_bar_counter_fancy_hide_bar():
    c1 = progression.UnsignedIntValue(val=0)
    c2 = progression.UnsignedIntValue(val=0)

    m1 = progression.UnsignedIntValue(val=0)

    c = [c1, c2]
    m = [m1, m1]
    maxc = 30
    t0 = time.time()

    try:
        with progression.ProgressBarCounterFancy(
            count=c, max_count=m, interval=INTERVAL
        ) as sc:
            sc.start()
            while True:
                i = np.random.randint(0, 2)
                with c[i].get_lock():
                    c[i].value += 1
                    if c[i].value > maxc:
                        sc.reset(i)

                time.sleep(INTERVAL / 60)
                if (time.time() - t0) > 2:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_info_line():
    c1 = progression.UnsignedIntValue(val=0)
    s = progression.StringValue(80)
    m1 = progression.UnsignedIntValue(val=30)
    try:
        with progression.ProgressBarFancy(
            count=c1, max_count=m1, interval=INTERVAL, info_line=s
        ) as sc:
            sc.start()
            while True:
                c1.value = c1.value + 1
                if c1.value > 10:
                    s.value = b"info_line\nline2"
                time.sleep(INTERVAL / 60)
                if c1.value >= m1.value:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_change_prepend():
    c1 = progression.UnsignedIntValue(val=0)
    m1 = progression.UnsignedIntValue(val=30)
    try:
        with progression.ProgressBarFancy(
            count=c1, max_count=m1, interval=INTERVAL
        ) as sc:
            sc.start()
            while True:
                c1.value = c1.value + 1
                sc.prepend = [str(c1.value)]
                time.sleep(INTERVAL / 60)
                if c1.value >= m1.value:
                    break
    finally:
        _kill_pid(sc.getpid())


def test_stop_progress_with_large_interval():
    c1 = progression.UnsignedIntValue(val=0)
    m1 = progression.UnsignedIntValue(val=10)
    try:
        with progression.ProgressBarFancy(
            count=c1, max_count=m1, interval=10 * INTERVAL
        ) as sc:
            sc.start()
            while True:
                c1.value = c1.value + 1
                time.sleep(INTERVAL / 5)
                if c1.value >= m1.value:
                    break
            print("done inner loop")
    finally:
        _kill_pid(sc.getpid())

    print("done progression")


def test_get_identifier():
    for bold in [True, False]:
        for name in [None, "test"]:
            for pid in [None, "no PID"]:
                id = progression.get_identifier(name=name, pid=pid, bold=bold)
                print(id)


def test_catch_subprocess_error():
    def f_error():
        raise RuntimeError("my ERROR")

    def f_no_error():
        print("no error")

    try:
        with progression.Loop(func=f_no_error, interval=INTERVAL) as loop:
            loop.start()
            time.sleep(0.5 * INTERVAL)

        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    finally:
        _kill_pid(loop.getpid())

    try:
        with progression.Loop(func=f_error, interval=INTERVAL) as loop:
            loop.start()
            time.sleep(0.5 * INTERVAL)

        _safe_assert_not_loop_is_alive(loop)
        print("[+] normal loop stopped")
    except progression.LoopExceptionError:
        print("noticed that an exception occurred")

    finally:
        _kill_pid(loop.getpid())


def test_stopping_loop():
    def f():
        return True

    try:
        with progression.Loop(func=f, interval=INTERVAL) as loop:
            loop.start()
            time.sleep(1.5 * INTERVAL)

            print("this loop has stopped it self, because it returned True")
            _safe_assert_not_loop_is_alive(loop)

    finally:
        _kill_pid(loop.getpid())


def test_humanize_time():
    assert progression.humanize_time(0.1234567) == "123.46ms", "{}".format(
        progression.humanize_time(0.1234567)
    )
    assert progression.humanize_time(5.1234567) == "5.12s", "{}".format(
        progression.humanize_time(5.1234567)
    )
    assert progression.humanize_time(123456) == "34:17:36", "{}".format(
        progression.humanize_time(123456)
    )


def f_wrapper_termination(shared_pid):
    class Signal_to_sys_exit(object):
        def __init__(self, signals=[signal.SIGINT, signal.SIGTERM]):
            for s in signals:
                signal.signal(s, self._handler)

        def _handler(self, signal, frame):
            print(
                "PID {}: received signal {} -> call sys.exit -> raise SystemExit".format(
                    os.getpid(), progression.signal_dict[signal]
                )
            )
            sys.exit("exit due to signal {}".format(progression.signal_dict[signal]))

    Signal_to_sys_exit()

    def loopf(shared_pid):
        shared_pid.value = os.getpid()
        print(time.clock())

    with progression.Loop(
        func=loopf, args=(shared_pid,), sigint="ign", sigterm="ign", interval=0.3
    ) as l:
        l.start()
        while True:
            time.sleep(1)


def test_wrapper_termination():
    progression.log.setLevel(logging.DEBUG)
    shared_pid = progression.UnsignedIntValue()
    p = mp.Process(target=f_wrapper_termination, args=(shared_pid,))
    p.start()
    time.sleep(2)
    p.terminate()
    p.join(5)

    pid = shared_pid.value

    if pid != 0:
        if psutil.pid_exists(pid):
            p = psutil.Process(pid)
            while p.is_running():
                print("pid {} is still running, sigkill".format(pid))
                p.send_signal(signal.SIGKILL)
                time.sleep(0.1)

            print("pid {} has stopped now".format(pid))
            assert False, "the loop process was still running!"


def test_codecov_subprocess_test():
    """
    it turns out that this line is accounted for by pytest-cov (2.7, 3.4)
    """

    def f():
        progression.codecov_subprocess_check()

    p = mp.Process(target=f)
    p.start()
    p.join(1)
    if p.is_alive():
        p.terminate()


def test_ESC_SEQ():
    tr = progression.terminal
    s = tr.ESC_BOLD + "["

    s = (
        "hal"
        + tr.ESC_BOLD
        + "lo "
        + tr.ESC_MOVE_LINE_DOWN(4)
        + "welt"
        + tr.ESC_LIGHT_BLUE
    )
    s_stripped = tr.remove_ESC_SEQ_from_string(s)
    assert s_stripped == "hallo welt"

    for e in tr.ESC_SEQ_SET:
        s += e

    s_stripped = tr.remove_ESC_SEQ_from_string(s)
    assert s_stripped == "hallo welt"

    s = (
        "hallo "
        + tr.ESC_BLUE
        + "w"
        + tr.ESC_BOLD
        + "el"
        + tr.ESC_CYAN
        + "t"
        + tr.ESC_NO_CHAR_ATTR
        + "\n"
        + "hallo "
        + tr.ESC_BLUE
        + "w"
        + tr.ESC_BOLD
        + "el"
        + tr.ESC_CYAN
        + "t"
    )

    s_html = tr.ESC_SEQ_to_HTML(s)
    print(s_html)


def test_show_stat():
    kwargs = {
        "counter_count": [progression.UnsignedIntValue(10)],
        "counter_speed": [progression.UnsignedIntValue(1)],
        "init_time": 0,
    }

    pre = "pre str: "

    progression.show_stat_ProgressBar(
        count_value=0,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBar(
        count_value=5,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBar(
        count_value=10,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )

    progression.show_stat_ProgressBar(
        count_value=0,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBar(
        count_value=5,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBar(
        count_value=10,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )

    progression.show_stat_ProgressBarCounter(
        count_value=0,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounter(
        count_value=5,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounter(
        count_value=10,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )

    progression.show_stat_ProgressBarCounter(
        count_value=0,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounter(
        count_value=5,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounter(
        count_value=10,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )

    progression.show_stat_ProgressBarFancy(
        count_value=0,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBarFancy(
        count_value=5,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBarFancy(
        count_value=80 - len(pre) - 2 - 1,
        max_count_value=80 - len(pre) - 2,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBarFancy(
        count_value=1,
        max_count_value=80 - len(pre) - 2,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBarFancy(
        count_value=10,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )

    progression.show_stat_ProgressBarFancy(
        count_value=0,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBarFancy(
        count_value=5,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )
    progression.show_stat_ProgressBarFancy(
        count_value=10,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=None,
    )

    progression.show_stat_ProgressBarCounterFancy(
        count_value=0,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounterFancy(
        count_value=5,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounterFancy(
        count_value=10,
        max_count_value=10,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )

    progression.show_stat_ProgressBarCounterFancy(
        count_value=0,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounterFancy(
        count_value=5,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )
    progression.show_stat_ProgressBarCounterFancy(
        count_value=10,
        max_count_value=0,
        prepend=pre,
        speed=1.1,
        tet=11,
        ttg=100,
        width=80,
        i=0,
        **kwargs
    )


def test_example_StdoutPipe():
    import sys
    from multiprocessing import Pipe
    from progression import StdoutPipe

    conn_recv, conn_send = Pipe(False)
    sys.stdout = StdoutPipe(conn_send)

    print("hallo welt", end="")  # this is no going through the pipe
    msg = conn_recv.recv()
    sys.stdout = sys.__stdout__

    print(msg)
    assert msg == "hallo welt"


def test_fork():
    f = lambda: print("f")
    p = mp.Process(target=f)
    p.start()
    p.join(1)


if __name__ == "__main__":
    #    progression.log.setLevel(logging.DEBUG)
    func = [
        # test_humanize_time,
        # test_codecov_subprocess_test,
        # test_wrapper_termination,
        # test_catch_subprocess_error,
        # test_prefix_logger,
        # test_loop_basic,
        # test_loop_start_stop,
        # test_loop_start_timeout,
        # test_loop_signals,
        # test_loop_normal_stop,
        # test_loop_need_sigterm_to_stop,
        # test_loop_need_sigkill_to_stop,
        # test_loop_stdout_pipe,
        # test_loop_pause,
        test_loop_logging,
        # test_loop_why_with_statement,
        # test_loop_with_error_in_func,
        # test_progress_bar_with_statement,
        # test_progress_bar_multi,
        # test_status_counter,
        # test_status_counter_multi,
        # test_intermediate_prints_while_running_progess_bar,
        # test_intermediate_prints_while_running_progess_bar_multi,
        # test_progress_bar_counter,
        # test_progress_bar_counter_non_max,
        # test_progress_bar_counter_hide_bar,
        # test_progress_bar_slow_change,
        # test_progress_bar_start_stop,
        # test_progress_bar_fancy,
        # test_progress_bar_multi_fancy,
        # test_progress_bar_fancy_small,
        # test_progress_bar_counter_fancy,
        # test_progress_bar_counter_fancy_non_max,
        # test_progress_bar_counter_fancy_hide_bar,
        # test_info_line,
        # test_change_prepend,
        # test_stop_progress_with_large_interval,
        # test_get_identifier,
        # test_stopping_loop,
        # test_ESC_SEQ,
        # test_example_StdoutPipe,
        # test_show_stat,
        # test_fork,
        lambda: print("END"),
    ]

    for f in func:
        print()
        print("#" * 80)
        print("##  {}".format(f.__name__))
        print()
        f()
        time.sleep(1)
