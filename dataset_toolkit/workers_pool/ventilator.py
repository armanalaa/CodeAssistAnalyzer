#
# Uber, Inc. (c) 2018
#
from time import sleep

import random
import threading
from abc import ABCMeta, abstractmethod

_VENTILATION_INTERVAL = 0.01


class Ventilator(object):
    """Manages items to be ventilated to a worker pool"""
    __metaclass__ = ABCMeta

    def __init__(self, ventilate_fn):
        self._ventilate_fn = ventilate_fn

    @abstractmethod
    def start(self):
        """Starts the ventilator, beginning to ventilate to the worker pool after this call.
        Therefore the worker pool must be ready to receive ventilated items"""
        return

    @abstractmethod
    def processed_item(self):
        """A callback for the worker pool to tell the ventilator that it has processed an item from the ventilation
        queue. This allows the ventilator to know how many items are currently on the ventilation queue.
        This function should not have a return value"""
        pass

    @abstractmethod
    def completed(self):
        """Return whether the ventilator has completed ventilating all items it expects to ever ventilate"""
        return

    @abstractmethod
    def stop(self):
        """Tell the ventilator to stop ventilating"""
        return


class ConcurrentVentilator(Ventilator):
    """
    A ConcurrentVentilator handles ventilation of a pre-determined list of items to a worker pool and performs
    the ventilation concurrently in a separate thread. It will keep track of how many items are currently in the
    ventilation queue and prevent it from monotonically increasing in order to prevent boundless memory requirements.
    It allows for multiple (or infinite) iterations of the ventilating the items, optionally randomizing the order of
    items being ventilated at the start of each iteration.
    """

    def __init__(self,
                 ventilate_fn,
                 items_to_ventilate,
                 iterations=1,
                 randomize_item_order=False,
                 max_ventilation_queue_size=None,
                 ventilation_interval=_VENTILATION_INTERVAL):
        """
        Constructor for a concurrent ventilator.

        :param ventilate_fn: The function to be called when ventilating. Usually the worker pool ventilate function.
        :param items_to_ventilate: (list[dict]) The list of items to ventilate. Each item is a dict denoting the
                **kwargs eventually passed to a worker process function
        :param iterations: (int) How many iterations through items_to_ventilate should be done and ventilated to the
                worker pool. For example if set to 2 each item in items_to_ventilate will be ventilated 2 times. If
                'None' is passed, the ventilator will continue ventilating forever.
        :param randomize_item_order: (bool) Whether to randomize the item order in items_to_ventilate. This will be
                done on every individual iteration.
        :param max_ventilation_queue_size: (int) The maximum number of items to be stored in the ventilation queue.
                The higher this number, the higher potential memory requirements. By default it will use the size
                of items_to_ventilate since that can definitely be held in memory.
        :param ventilation_interval: (float in seconds) How much time passes between checks on whether something can be
                ventilated (when the ventilation queue is considered full).
        """
        super(ConcurrentVentilator, self).__init__(ventilate_fn)

        if iterations is not None and (not isinstance(iterations, int) or iterations < 1):
            raise ValueError('iterations must be positive integer or None')

        if not isinstance(items_to_ventilate, list) or any(not isinstance(item, dict) for item in items_to_ventilate):
            raise ValueError('items_to_ventilate must be a list of dicts')

        self._items_to_ventilate = items_to_ventilate
        self._iterations_remaining = iterations
        self._randomize_item_order = randomize_item_order

        # For the default max ventilation queue size we will use the size of the items to ventilate
        self._max_ventilation_queue_size = max_ventilation_queue_size or len(items_to_ventilate)
        self._ventilation_interval = ventilation_interval

        self._current_item_to_ventilate = 0
        self._ventilation_thread = None
        self._ventilated_items_count = 0
        self._processed_items_count = 0

    def start(self):
        # Start the ventilation thread
        self._ventilation_thread = threading.Thread(target=self._ventilate, args=())
        self._ventilation_thread.daemon = True
        self._ventilation_thread.start()

    def processed_item(self):
        self._processed_items_count += 1

    def completed(self):
        return self._iterations_remaining == 0 or not self._items_to_ventilate

    def _ventilate(self):
        while True:
            # Stop condition is when no iterations are remaining or there are no items to ventilate
            if self.completed():
                break

            # If we are ventilating the first item, we check if we would like to randomize the item order
            if self._current_item_to_ventilate == 0 and self._randomize_item_order:
                random.shuffle(self._items_to_ventilate)

            # Block until queue has room, but use continue to allow for checking if stop has been called
            if self._ventilated_items_count - self._processed_items_count >= self._max_ventilation_queue_size:
                sleep(self._ventilation_interval)
                continue

            item_to_ventilate = self._items_to_ventilate[self._current_item_to_ventilate]
            self._ventilate_fn(**item_to_ventilate)
            self._current_item_to_ventilate += 1
            self._ventilated_items_count += 1

            if self._current_item_to_ventilate >= len(self._items_to_ventilate):
                self._current_item_to_ventilate = 0
                # If iterations was set to None, that means we will iterate until stop is called
                if self._iterations_remaining is not None:
                    self._iterations_remaining -= 1

    def stop(self):
        self._iterations_remaining = 0
        if self._ventilation_thread:
            self._ventilation_thread.join()
            self._ventilation_thread = None
