#
# Uber, Inc. (c) 2017
#

from __future__ import print_function

import time
import unittest

import numpy as np

from dataset_toolkit.workers_pool import EmptyResultError, TimeoutWaitingForResultError
from dataset_toolkit.workers_pool.dummy_pool import DummyPool
from dataset_toolkit.workers_pool.process_pool import ProcessPool
from dataset_toolkit.workers_pool.tests.stub_workers import CoeffMultiplierWorker, \
    WorkerIdGeneratingWorker, WorkerMultiIdGeneratingWorker, SleepyWorkerIdGeneratingWorker, \
    ExceptionGeneratingWorker_5, SleepyDoingNothingWorker, PreprogrammedReturnValueWorker
from dataset_toolkit.workers_pool.thread_pool import ThreadPool


class TestWorkersPool(unittest.TestCase):

    def _passing_args_impl(self, pool_class_factory):
        """Pass a coefficient to the workers and make it multiply the input with this coefficient"""
        DELTA = 12
        ITERATIONS = 100
        pool = pool_class_factory()

        pool.start(CoeffMultiplierWorker, {'coeff': DELTA})
        for i in range(ITERATIONS):
            pool.ventilate(message='Vent data {}'.format(i), value=i)

        all_results = [pool.get_results() for _ in range(ITERATIONS)]
        self.assertEqual({DELTA}, set(np.diff(sorted(all_results))))

        pool.stop()
        pool.join()

    def test_passing_args_processes(self):
        self._passing_args_impl(lambda: ProcessPool(10))

    def test_passing_args_threads(self):
        self._passing_args_impl(lambda: ThreadPool(10))

    def test_passing_args_dummy(self):
        self._passing_args_impl(lambda: DummyPool())

    def test_all_workers_are_active_processes(self):
        """Check that the work is distributed among all workers"""
        WORKERS_COUNT = 10

        # Testing only ProcessPool since only it has the mechanism that waits for all workers to come online before
        # start finishes
        pool = ProcessPool(WORKERS_COUNT)

        pool.start(WorkerIdGeneratingWorker)
        for i in range(100):
            pool.ventilate()

        active_worker_ids = [pool.get_results() for _ in range(100)]
        self.assertEqual(set(range(WORKERS_COUNT)), set(active_worker_ids))

        pool.stop()
        pool.join()

    def block_on_get_results_impl(self, pool_class):
        """Check that the get_results blocking timeout works"""

        # COULD BECOME A FLAKY TEST SINCE RELIES ON TIME
        WORKERS_COUNT = 10
        pool = pool_class(WORKERS_COUNT)

        pool.start(SleepyWorkerIdGeneratingWorker)
        tic = time.time()

        pool.ventilate()
        pool.get_results()

        toc = time.time()
        # Leave a huge slack so we don't get a flaky test
        self.assertTrue(np.isclose(1.0, toc - tic, atol=0.5))

        pool.stop()
        pool.join()

    def timeout_while_waiting_on_results_impl(self, pool_class):
        """Check that timeout error would occur worker don't write results to the results queue in time"""

        # COULD BECOME A FLAKY TEST SINCE RELIES ON TIME
        WORKERS_COUNT = 5
        pool = pool_class(WORKERS_COUNT)

        pool.start(SleepyDoingNothingWorker, 3)

        pool.ventilate()
        with self.assertRaises(TimeoutWaitingForResultError):
            pool.get_results(timeout=0.1)

        pool.stop()
        pool.join()

    def raise_empty_result_error_on_get_results_impl(self, pool_class):
        """Check that the get_results returns None when there is no work left to do"""

        # COULD BECOME A FLAKY TEST SINCE RELIES ON TIME
        WORKERS_COUNT = 10
        pool = pool_class(WORKERS_COUNT)

        pool.start(WorkerMultiIdGeneratingWorker)

        with self.assertRaises(EmptyResultError):
            pool.get_results()

        pool.ventilate()
        self.assertIsNotNone(pool.get_results())
        self.assertIsNotNone(pool.get_results())

        with self.assertRaises(EmptyResultError):
            pool.get_results()

        pool.stop()
        pool.join()

    def test_block_on_get_results_processes(self):
        self.block_on_get_results_impl(ProcessPool)

    def test_block_on_get_results_threads(self):
        self.block_on_get_results_impl(ThreadPool)

    def test_block_on_get_results_dummy(self):
        self.block_on_get_results_impl(DummyPool)

    def test_return_none_on_get_results_process(self):
        self.raise_empty_result_error_on_get_results_impl(ProcessPool)

    def test_return_none_on_get_results_threads(self):
        self.raise_empty_result_error_on_get_results_impl(ThreadPool)

    def test_return_none_on_get_results_dummy(self):
        self.raise_empty_result_error_on_get_results_impl(DummyPool)

    def test_timeout_while_waiting_on_results_thread(self):
        self.timeout_while_waiting_on_results_impl(ThreadPool)

    def test_timeout_while_waiting_on_results_process(self):
        self.timeout_while_waiting_on_results_impl(ProcessPool)

    def test_stop_when_result_queue_is_full(self):
        """Makes sure we don't block indefinitely on ventilator queue"""
        SLEEP_DELTA = 0.01
        TIMEOUT = 20
        QUEUE_SIZE = 2

        pool = ThreadPool(10, results_queue_size=QUEUE_SIZE)
        pool.start(WorkerIdGeneratingWorker)

        for i in range(100):
            pool.ventilate()

        cumulative_wait = 0
        while pool.results_qsize() != QUEUE_SIZE:
            time.sleep(SLEEP_DELTA)
            cumulative_wait += SLEEP_DELTA
            # Make sure we wait no longer than the timeout. Otherwise, something is very wrong
            self.assertLess(cumulative_wait, TIMEOUT, msg='Timeout while waiting for the results queue to fill')

        # No need to read from the queue. We are testing ability to exit when workers might be blocked on the
        # results queue

        pool.stop()
        pool.join()

    def test_dummy_pool_should_process_tasks_in_fifo_order(self):
        """Check that the dummy pool processes in fifo order"""
        pool = DummyPool()
        pool.start(CoeffMultiplierWorker, {'coeff': 1})

        # Important to try a case where a worker generates multiple results. That's why we have some irregular
        # ventilate/get_results pattern in this test
        actual_output = []

        pool.ventilate(message='dummy message', value=[0, 1])
        pool.ventilate(message='dummy message', value=2)

        actual_output.append(pool.get_results())

        pool.ventilate(message='dummy message', value=[3, 4])

        actual_output.append(pool.get_results())
        actual_output.append(pool.get_results())
        actual_output.append(pool.get_results())
        actual_output.append(pool.get_results())

        self.assertEqual(actual_output, [0, 1, 2, 3, 4])

    def _test_exception_in_worker_impl(self, pool, num_to_ventilate):
        """ Test exception handler in worker. Pool should be terminated """
        # exception should be propagated to calling thread
        pool.start(ExceptionGeneratingWorker_5)
        for i in xrange(num_to_ventilate):
            pool.ventilate("Datanum_%d" % i)
        with self.assertRaises(ValueError):
            pool.get_results()

    def test_exception_in_worker_thread(self):
        """ Test exception handler in thread pool """
        QUEUE_SIZE = 100
        self._test_exception_in_worker_impl(ThreadPool(10, results_queue_size=QUEUE_SIZE), QUEUE_SIZE)

    def test_exception_in_worker_process(self):
        """ Test exception handler in process pool """

        # NOTE: The process pool has a problem that if the workers are throwing exceptions, their
        # zmq sockets will be closed and there is some race condition that can cause the ventilate
        # to raise an exception. Only ventilating a single time guarantees that it will be properly
        # sent to a worker before it has exited due to an exception
        self._test_exception_in_worker_impl(ProcessPool(10), 1)

    def test_exception_in_all_worker_process(self):
        """ Tests that when all worker processes have exited, zmq will properly throw an exception
         when trying to ventilate instead of blocking indefinitely"""
        pool = ProcessPool(5)
        pool.start(ExceptionGeneratingWorker_5)
        with self.assertRaises(RuntimeError):
            for _ in range(10000):
                pool.ventilate("Datanum")
                time.sleep(.1)

    def test_exception_reusing_thread_pool(self):
        WORKERS_COUNT = 10
        pool = ThreadPool(WORKERS_COUNT)
        pool.start(WorkerIdGeneratingWorker)
        with self.assertRaises(EmptyResultError):
            pool.get_results()
        pool.ventilate()
        self.assertIsNotNone(pool.get_results())
        with self.assertRaises(EmptyResultError):
            pool.get_results()
        pool.stop()
        pool.join()
        with self.assertRaises(RuntimeError) as e:
            pool.start(WorkerIdGeneratingWorker)
        self.assertTrue('ThreadPool({}) cannot be reused! stop_event set? {}'
                        .format(WORKERS_COUNT, True) in e.exception.message)

    def test_worker_produces_no_results(self):
        """Check edge case, when workers consistently does not produce results"""
        # 10000 is an interesting case as in the original implementation it caused stack overflow
        for ventilate_count in [10, 10000]:
            for pool in [DummyPool(), ThreadPool(2), ProcessPool(2)]:
                pool.start(PreprogrammedReturnValueWorker, ventilate_count * [[]])
                for i in range(ventilate_count):
                    pool.ventilate('not_important')

                with self.assertRaises(EmptyResultError):
                    pool.get_results()

                pool.stop()
                pool.join()

    def test_worker_produces_some_results(self):
        """Check edge case, when workers consistently does not produce results"""
        # 10000 is an interesting case as in the original implementation it caused stack overflow
        VENTILATE_COUNT = 4
        for pool in [DummyPool(), ThreadPool(1), ProcessPool(1)]:
            pool.start(PreprogrammedReturnValueWorker, [[], [], [42], []])
            for i in range(VENTILATE_COUNT):
                pool.ventilate('not_important')

            self.assertEqual(42, pool.get_results())
            with self.assertRaises(EmptyResultError):
                pool.get_results()

            pool.stop()
            pool.join()


if __name__ == '__main__':
    # Delegate to the test framework.
    unittest.main()
