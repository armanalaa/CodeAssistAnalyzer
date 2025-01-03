#
# Uber, Inc. (c) 2017
#
import os
import pickle
import subprocess
import sys
from tempfile import mkstemp


def exec_in_new_process(func, *args, **kargs):
    """Launches a function in a separate process. Takes variable number of arguments which are passed to the function.
    The process IS NOT FORKED by 'exec'ed.

    :param func: Function to be executed in a separate process.
    :param args: position arguments passed to the func
    :param kargs: named arguments passed to the func
    :return:
    """

    # Store function handle and arguments into a pickle
    new_process_runnable_handle, new_process_runnable_file = mkstemp(suffix='runnable')
    with os.fdopen(new_process_runnable_handle, 'w') as f:
        pickle.dump((func, args, kargs), f)

    bootstrap_package_name = '{}.{}'.format(__package__, os.path.splitext(os.path.basename(__file__))[0])
    # Popen this script (__main__) below will be an entry point
    process = subprocess.Popen(args=[sys.executable,
                                     '-m',
                                     bootstrap_package_name,
                                     new_process_runnable_file],
                               executable=sys.executable)
    return process


if __name__ == '__main__':
    # An entry point to the newely executed process.
    # Will unpickle function handle and arguments and call the function.
    if len(sys.argv) != 2:
        raise RuntimeError('Expected a single command line argument')
    new_process_runnable_file = sys.argv[1]

    with open(new_process_runnable_file, 'rb') as f:
        func, args, kargs = pickle.load(f)

    # Don't need the pickle file with the runable. Cleanup.
    os.remove(new_process_runnable_file)

    func(*args, **kargs)
