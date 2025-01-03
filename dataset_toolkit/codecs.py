#
# Uber, Inc. (c) 2017
#

"""A set of dataframe-column-codecs complements limited data type variety of spark/pyarrow supported datatypes. Enables
storing numpy multidimensional arrays as well as compressed images into spark dataframes (transitively to parquet files)

NOTE: Due to the way unischema is stored alongside dataset (with pickling), changing any of these codecs class names
and fields can result in reader breakages.
"""

import cStringIO as StringIO
from abc import abstractmethod

import numpy as np
from PIL import Image
from pyspark.sql.types import BinaryType, LongType, IntegerType, ShortType, ByteType, StringType


class DataframeColumnCodec(object):
    @abstractmethod
    def encode(self, unischema_field, array):
        raise RuntimeError('Abstract method was called')

    @abstractmethod
    def decode(self, unischema_field, value):
        raise RuntimeError('Abstract method was called')

    @abstractmethod
    def spark_dtype(self):
        """Spark datatype to be used for underlying storage"""
        raise RuntimeError('Abstract method was called')


class CompressedImageCodec(DataframeColumnCodec):
    def __init__(self, format='png'):
        """CompressedImageCodec would compress/encompress images.

        :param format: any format string supported by PIL. e.g. 'png', 'jpeg'
        """
        self._format = format

    def encode(self, unischema_field, image_rgb):
        image = Image.fromarray(image_rgb)
        output = StringIO.StringIO()
        image.save(output, format=self._format)
        contents = output.getvalue()
        output.close()
        return bytearray(contents)

    def decode(self, unischema_field, value):
        image_data = StringIO.StringIO(value)
        image = Image.open(image_data)
        numpy_image = np.asarray(image)
        return numpy_image

    def spark_dtype(self):
        return BinaryType()


class NdarrayCodec(DataframeColumnCodec):
    """Encodes numpy ndarray into a spark dataframe field"""

    def encode(self, unischema_field, array):
        expected_dtype = unischema_field.numpy_dtype
        if isinstance(array, np.ndarray):
            if expected_dtype != array.dtype.type:
                raise ValueError('Unexpected type of {} feature. '
                                 'Expected {}. Got {}'.format(unischema_field.name, expected_dtype, array.dtype))

            expected_shape = unischema_field.shape
            if not _is_compliant_shape(array.shape, expected_shape):
                raise ValueError('Unexpected dimensions of {} feature. '
                                 'Expected {}. Got {}'.format(unischema_field.name, expected_shape, array.shape))
        else:
            raise ValueError('Unexpected type of {} feature. '
                             'Expected ndarray of {}. Got {}'.format(unischema_field.name, expected_dtype, type(array)))

        memfile = StringIO.StringIO()
        np.save(memfile, array)
        return bytearray(memfile.getvalue())

    def decode(self, unischema_field, value):
        memfile = StringIO.StringIO(value)
        return np.load(memfile)

    def spark_dtype(self):
        return BinaryType()


class ScalarCodec(DataframeColumnCodec):
    """Encodes a scalar into a spark dataframe field"""

    def __init__(self, spark_type):
        """Constructs a codec
        :param spark_type: an instance of a *Type object from pyspark.sql.types
        """
        self._spark_type = spark_type

    def encode(self, unischema_field, value):
        if isinstance(self._spark_type, (ByteType, ShortType, IntegerType, LongType)):
            return int(value)
        if isinstance(self._spark_type, StringType):
            if not isinstance(value, basestring):
                raise ValueError(
                    'Expected a string value for field {}. Got type {}'.format(unischema_field.name, type(value)))
        return value

    def decode(self, unischema_field, encoded):
        return unischema_field.numpy_dtype(encoded)

    def spark_dtype(self):
        return self._spark_type


def _is_compliant_shape(a, b):
    """Compares shapes of two arguments.

    If size of a dimensions is None, this dimension size is ignored.
    Example:
        assert _is_compliant_shape((1, 2, 3), (1, 2, 3))
        assert _is_compliant_shape((1, 2, 3), (1, None, 3))
        assert not _is_compliant_shape((1, 2, 3), (1, 10, 3))
        assert not _is_compliant_shape((1, 2), (1,))

    :return: True, if the shapes are compliant
    """
    if len(a) != len(b):
        return False
    for i in xrange(len(a)):
        if a[i] and b[i]:
            if a[i] != b[i]:
                return False
    return True
