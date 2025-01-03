#
# Uber, Inc. (c) 2017
#
import unittest
from collections import namedtuple
from decimal import Decimal
from shutil import rmtree
from tempfile import mkdtemp

import numpy as np
import tensorflow as tf
from concurrent.futures import ThreadPoolExecutor

from dataset_toolkit.reader import Reader
from dataset_toolkit.sequence import Sequence
from dataset_toolkit.tests.test_common import create_test_dataset, TestSchema
from dataset_toolkit.tf_utils import _sanitize_field_tf_types, _numpy_to_tf_dtypes, \
    _schema_to_tf_dtypes, tf_tensors
from dataset_toolkit.unischema import Unischema, UnischemaField
from dataset_toolkit.workers_pool.dummy_pool import DummyPool


class SanitizeTfTypesTest(unittest.TestCase):

    def test_empty_dict(self):
        # Check two types that should be promoted/converted (uint16 and Decimal) and one that should not be
        # modified (int32)
        sample_input_dict = {
            'int32': np.asarray([-2 ** 31, 0, 100, 2 ** 31 - 1], dtype=np.int32),
            'uint16': np.asarray([0, 2, 2 ** 16 - 1], dtype=np.uint16),
            'Decimal': Decimal(1234) / Decimal(10),
        }

        TestNamedTuple = namedtuple('TestNamedTuple', sample_input_dict.keys())
        sample_input_tuple = TestNamedTuple(**sample_input_dict)
        sanitized_tuple = _sanitize_field_tf_types(sample_input_tuple)

        np.testing.assert_equal(sanitized_tuple.int32.dtype, np.int32)
        np.testing.assert_equal(sanitized_tuple.uint16.dtype, np.int32)
        self.assertTrue(isinstance(sanitized_tuple.Decimal, basestring))

        np.testing.assert_equal(sanitized_tuple.int32, sample_input_dict['int32'])
        np.testing.assert_equal(sanitized_tuple.uint16, sample_input_dict['uint16'])
        np.testing.assert_equal(str(sanitized_tuple.Decimal), str(sample_input_dict['Decimal'].normalize()))


class SchemaToTfDtypesTest(unittest.TestCase):

    def test_decimal_conversion(self):
        self.assertEqual(_numpy_to_tf_dtypes(Decimal), tf.string)

    def test_uint16_promotion_to_int32(self):
        self.assertEqual(_numpy_to_tf_dtypes(np.uint16), tf.int32)

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            _numpy_to_tf_dtypes(np.uint64)

    def test_schema_to_dtype_list(self):
        TestSchema = Unischema('TestSchema', [
            UnischemaField('int32', np.int32, (), None, False),
            UnischemaField('uint8', np.uint8, (), None, False),
            UnischemaField('uint16', np.uint16, (), None, False),
            UnischemaField('Decimal', Decimal, (), None, False),
        ])

        actual_tf_dtype_list = _schema_to_tf_dtypes(TestSchema)
        # Note that the order of the fields is defined by alphabetical order of keys and always sorted by Unischema
        # to avoid ambiguity
        #  [Decimal,   int32,    uint16,   uint8] <- alphabetical order
        #  [tf.string, tf.int32, tf.int32, tf.uint8]
        np.testing.assert_equal(actual_tf_dtype_list, [tf.string, tf.int32, tf.int32, tf.uint8])


class TestTfTensors(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initializes dataset once per test. All tests in this class will use the same fake dataset."""
        # Write a fake dataset to this location
        cls._dataset_dir = mkdtemp('end_to_end_dataset_toolkit')
        cls._dataset_url = 'file://{}'.format(cls._dataset_dir)
        ROWS_COUNT = 1000
        cls._dataset_dicts = create_test_dataset(cls._dataset_url, range(ROWS_COUNT))

    @classmethod
    def tearDownClass(cls):
        # Remove everything created with "get_temp_dir"
        rmtree(cls._dataset_dir)

    def _read_from_tf_tensors(self, count, shuffling_queue_capacity, min_after_dequeue, sequence):
        """Used by several test cases. Reads a 'count' rows using reader.

        The reader is configured without row-group shuffling and guarantees deterministic order of rows up to the
        results queue TF shuffling which is controlled by 'shuffling_queue_capacity', 'min_after_dequeue' arguments.

        The function returns a tuple with: (actual data read from the dataset, a TF tensor returned by the reader)
        """

        # Nullable fields can not be read by tensorflow (what would be the dimension of a tensor for null data?)
        fields = set(TestSchema.fields.values()) - {TestSchema.matrix_nullable}

        reader = Reader(schema_fields=fields, dataset_url=self._dataset_url, reader_pool=DummyPool(), shuffle=False,
                        sequence=sequence)

        row_tensors = tf_tensors(reader, shuffling_queue_capacity=shuffling_queue_capacity,
                                 min_after_dequeue=min_after_dequeue)

        # Read a bunch of entries from the dataset and compare the data to reference
        with tf.Session() as sess:
            sess.run([tf.global_variables_initializer(), tf.local_variables_initializer()])

            coord = tf.train.Coordinator()
            threads = tf.train.start_queue_runners(coord=coord, start=True)

            # Collect all the data we need from 'count' number of reads
            rows_data = [sess.run(row_tensors) for _ in range(count)]

            coord.request_stop()
            coord.join(threads)

        reader.stop()
        reader.join()

        return rows_data, row_tensors

    def _assert_all_tensors_have_shape(self, row_tensors):
        """Asserts that all elements in row_tensors list/tuple have static shape."""
        for column in row_tensors:
            self.assertIsNotNone(column.get_shape().dims)

    def _assert_expected_rows_data(self, rows_data):
        """Asserts all elements of rows_data list of rows match reference data used to create the dataset"""
        for row_tuple in rows_data:

            # It is easier to work with dict as we will be indexing column names using strings
            row = row_tuple._asdict()

            # Find corresponding row in the reference data
            expected = next(d for d in self.__class__._dataset_dicts if d['id'] == row['id'])

            # Check equivalence of all values between a checked row and a row from reference data
            for column_name, value in row.iteritems():
                if isinstance(expected[column_name], Decimal):
                    np.testing.assert_equal(expected[column_name], Decimal(row[column_name]))
                else:
                    np.testing.assert_equal(expected[column_name], row[column_name])

    def test_simple_read_tensorflow(self):
        """Read couple of rows. Make sure all tensors have static shape sizes assigned and the data matches reference
        data"""
        rows_data, row_tensors = \
            self._read_from_tf_tensors(count=30, shuffling_queue_capacity=0, min_after_dequeue=0, sequence=None)

        # Make sure we have static shape info for all fields
        self._assert_all_tensors_have_shape(row_tensors)
        self._assert_expected_rows_data(rows_data)

    def test_shuffling_queue(self):
        """Read data without tensorflow shuffling queue and with it. Check the the order is deterministic within
        unshuffled read and is random with shuffled read"""
        unshuffled_1, _ = self._read_from_tf_tensors(30, shuffling_queue_capacity=0, min_after_dequeue=0, sequence=None)
        unshuffled_2, _ = self._read_from_tf_tensors(30, shuffling_queue_capacity=0, min_after_dequeue=0, sequence=None)

        shuffled_1, shuffled_1_row_tensors = \
            self._read_from_tf_tensors(30, shuffling_queue_capacity=10, min_after_dequeue=0, sequence=None)
        shuffled_2, _ = \
            self._read_from_tf_tensors(30, shuffling_queue_capacity=10, min_after_dequeue=0, sequence=None)

        # Make sure we have static shapes and the data matches reference data (important since a different code path
        # is executed within tf_tensors when shuffling is specified
        self._assert_all_tensors_have_shape(shuffled_1_row_tensors)
        self._assert_expected_rows_data(shuffled_1)

        self.assertEqual([f.id for f in unshuffled_1],
                         [f.id for f in unshuffled_2])

        self.assertNotEqual([f.id for f in unshuffled_1],
                            [f.id for f in shuffled_2])

        self.assertNotEqual([f.id for f in shuffled_1],
                            [f.id for f in shuffled_2])

    def test_simple_sequence_read_tensorflow(self):
        """Read a single sequence. Make sure all shapes are set and the data read matches reference data"""
        SEQUENCE_LENGTH = 3

        # Expecting delta between ids to be 1. Setting 1.5 as upper bound
        sequence = Sequence(length=SEQUENCE_LENGTH, delta_threshold=1.5, timestamp_field='id')

        sequences, row_tensors_seq = \
            self._read_from_tf_tensors(30, shuffling_queue_capacity=0, min_after_dequeue=0, sequence=sequence)

        for row_tensors in row_tensors_seq.values():
            self._assert_all_tensors_have_shape(row_tensors)

        for one_sequence_dict in sequences:
            self._assert_expected_rows_data(one_sequence_dict.values())

    def test_shuffling_queue_with_sequences(self):
        """Read data without tensorflow shuffling queue and with it (no rowgroup shuffling). Read sequences
        Check the the order is deterministic within unshuffled read and is random with shuffled read"""
        SEQUENCE_LENGTH = 3

        # Expecting delta between ids to be 1. Setting 1.5 as upper bound
        sequence = Sequence(length=SEQUENCE_LENGTH, delta_threshold=1.5, timestamp_field='id')
        unshuffled_1, _ = self._read_from_tf_tensors(30, shuffling_queue_capacity=0, min_after_dequeue=0,
                                                     sequence=sequence)
        unshuffled_2, _ = self._read_from_tf_tensors(30, shuffling_queue_capacity=0, min_after_dequeue=0,
                                                     sequence=sequence)

        shuffled_1, shuffled_1_sequence = \
            self._read_from_tf_tensors(30, shuffling_queue_capacity=10, min_after_dequeue=0, sequence=sequence)
        shuffled_2, _ = \
            self._read_from_tf_tensors(30, shuffling_queue_capacity=10, min_after_dequeue=0, sequence=sequence)

        # shuffled_1_sequence is a dictionary of named tuple indexed by time:
        # {0: (tensor, tensor, tensor, ...),
        #  1: (tensor, tensor, tensor, ...),
        #  ...}
        for row_tensor in shuffled_1_sequence.values():
            self._assert_all_tensors_have_shape(row_tensor)

        # shuffled_1 is a list of dictionaries of named tuples indexed by time:
        # [{0: (tensor, tensor, tensor, ...),
        #  1: (tensor, tensor, tensor, ...),
        #  ...}
        # {0: (tensor, tensor, tensor, ...),
        #  1: (tensor, tensor, tensor, ...),
        #  ...},...
        # ]
        for one_sequence_dict in shuffled_1:
            self._assert_expected_rows_data(one_sequence_dict.values())

        def flatten(list_of_sequences):
            return [row for seq in list_of_sequences for row in seq.values()]

        self.assertEqual([f.id for f in flatten(unshuffled_1)],
                         [f.id for f in flatten(unshuffled_2)])

        self.assertNotEqual([f.id for f in flatten(unshuffled_1)],
                            [f.id for f in flatten(shuffled_2)])

        self.assertNotEqual([f.id for f in flatten(shuffled_1)],
                            [f.id for f in flatten(shuffled_2)])


if __name__ == '__main__':
    # Delegate to the test framework.
    unittest.main()
