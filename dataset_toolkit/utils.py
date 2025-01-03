#
# Uber, Inc. (c) 2017
#

import logging
import pyarrow

from multiprocessing import Pool

logger = logging.getLogger(__name__)


def run_in_subprocess(func, *args, **kwargs):
    """
    Run some code in a separate process and return the result. Once the code is done, terminate the process.
    This prevents a memory leak in the other process from affecting the current process.

    Gotcha: func must be a functioned defined at the top level of the module.
    :param kwargs: dict
    :param args: list
    :param func:
    :return:
    """
    pool = Pool(1)
    result = pool.apply(func, args=args, kwds=kwargs)

    # Probably not strictly necessary since terminate is called on GC, but it's not guaranteed when the pool will get
    # GC'd.
    pool.terminate()
    return result


def decode_row(row, schema):
    """
    Decode dataset row according to coding spec from unischema object
    :param row: dictionary with encodded values
    :param schema: unischema object
    :return:
    """
    decoded_row = dict()
    for field_name_unicode, encoded in row.iteritems():
        field_name = str(field_name_unicode)
        if field_name in schema.fields:
            if row[field_name] is not None:
                codec = schema.fields[field_name].codec
                decoded_row[field_name] = codec.decode(schema.fields[field_name], row[field_name])
            else:
                decoded_row[field_name] = None
    return decoded_row


def add_to_dataset_metadata(dataset, key, value):
    """
    Adds a key and value to the parquet metadata file of a parquet dataset.
    :param dataset: (ParquetDataset) parquet dataset
    :param key:     (str) key of metadata entry
    :param value:   (str) value of metadata
    """
    if not isinstance(dataset.paths, str):
        raise ValueError('Expected dataset.paths to be a single path, not a list of paths')

    metadata_file_path = dataset.paths.rstrip('/') + '/_metadata'

    # If the metadata file already exists, add to it.
    # Otherwise fetch the schema from one of the existing parquet files in the dataset
    if dataset.fs.exists(metadata_file_path):
        arrow_metadata = pyarrow.parquet.read_metadata(dataset.fs.open(metadata_file_path))
    else:
        arrow_metadata = dataset.pieces[0].get_metadata(lambda path: dataset.fs.open(path))
    base_schema = arrow_metadata.schema.to_arrow_schema()
    metadata_dict = base_schema.metadata
    metadata_dict[key] = value
    schema = base_schema.add_metadata(metadata_dict)

    with dataset.fs.open(metadata_file_path, 'wb') as metadata_file:
        pyarrow.parquet.write_metadata(schema, metadata_file)
