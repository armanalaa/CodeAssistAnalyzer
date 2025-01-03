#
# Uber, Inc. (c) 2018
#
import os
import unittest

import numpy as np

from dataset_toolkit.local_disk_cache import LocalDiskCache
from dataset_toolkit.tests.tempdir import temporary_directory

MB = 2 ** 20
KB = 2 ** 10


def _recursive_folder_size(folder):
    folder_size = 0
    for (path, dirs, files) in os.walk(folder):
        for file in files:
            filename = os.path.join(path, file)
            folder_size += os.path.getsize(filename)
    return folder_size


class TestDiskCache(unittest.TestCase):

    def test_simple_scalar_cache(self):
        """Testing trivial NullCache: should trigger value generating function on each run"""
        # with temporary_directory() as cache_dir:
        #     cache = LocalDiskCache(cache_dir, 1 * MB, 4)
        #     self.assertEqual(42, cache.get('some_key', lambda: 42))
        #     self.assertEqual(42, cache.get('some_key', lambda: 43))

    def test_size_limit_constraint(self):
        """Testing trivial NullCache: should trigger value generating function on each run"""
        with temporary_directory() as cache_dir:
            # We will write total of 5MB to the cache (50KB items x 100)
            RECORD_SIZE_BYTES = 50 * KB
            RECORDS_COUNT = 100

            a_record = np.random.randint(0, 255, (RECORD_SIZE_BYTES,), np.uint8)
            cache = LocalDiskCache(cache_dir, 1 * MB, RECORD_SIZE_BYTES, shards=1)

            for i in range(RECORDS_COUNT):
                cache.get('some_key_{}'.format(i), lambda: a_record)

            # Check that we are more or less within the size limit
            self.assertLess(_recursive_folder_size(cache_dir), 2 * MB)


if __name__ == '__main__':
    # Delegate to the test framework.
    unittest.main()
