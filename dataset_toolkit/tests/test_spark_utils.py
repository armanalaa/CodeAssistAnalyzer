#
# Uber, Inc. (c) 2017
#
import unittest
from shutil import rmtree
from tempfile import mkdtemp

import numpy as np
from dataset_toolkit.spark_utils import dataset_as_rdd
from dataset_toolkit.tests.test_common import create_test_dataset, TestSchema
from pyspark.sql import SparkSession


class TestSparkUtils(unittest.TestCase):

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

    def _get_spark_session(self):
        return SparkSession \
            .builder \
            .appName('dataset_toolkit_spark_utils_test') \
            .master('local[8]')\
            .getOrCreate()

    def test_simple_read_rdd(self):
        """Read dataset into spark rdd. Collects and makes sure they all return as expected"""
        spark = self._get_spark_session()
        rows = dataset_as_rdd(self._dataset_url, spark).collect()

        for row in rows:
            actual = dict(row._asdict())
            expected = next(d for d in self._dataset_dicts if d['id'] == actual['id'])
            np.testing.assert_equal(expected, actual)

        spark.stop()

    def test_reading_subset_of_columns(self):
        """Read subset of dataset fields into spark rdd. Collects and makes sure they all return as expected"""
        spark = self._get_spark_session()
        rows = dataset_as_rdd(self._dataset_url, spark, schema_fields=[TestSchema.id2, TestSchema.id]).collect()

        for row in rows:
            actual = dict(row._asdict())
            expected = next(d for d in self._dataset_dicts if d['id'] == actual['id'])
            np.testing.assert_equal(expected['id2'], actual['id2'])

        spark.stop()


if __name__ == '__main__':
    # Delegate to the test framework.
    unittest.main()
