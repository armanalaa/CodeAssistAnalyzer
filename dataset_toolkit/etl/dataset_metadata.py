#
# Uber, Inc. (c) 2018
#
import cPickle as pickle
import json
import os
import sys
from operator import attrgetter
from pyarrow import parquet as pq

from dataset_toolkit import utils
from dataset_toolkit.fs_utils import FilesystemResolver

ROW_GROUPS_PER_FILE_KEY = 'dataset-toolkit.num_row_groups_per_file.v1'
ROW_GROUPS_PER_FILE_KEY_ABSOLUTE_PATHS = 'dataset-toolkit.num_row_groups_per_file'
UNISCHEMA_KEY = 'dataset-toolkit.unischema.v1'


def add_dataset_metadata(dataset_url, spark_context, schema):
    """
    Adds all the metadata to the dataset needed to read the data using dataset toolkit
    :param dataset_url: (str) the url for the dataset (or a path if you would like to use the default hdfs config)
    :param spark_context: (SparkContext)
    :param schema: (Unischema) the schema for the dataset
    :return: None, upon successful completion the metadata file will exist
    """
    resolver = FilesystemResolver(dataset_url, spark_context._jsc.hadoopConfiguration())
    dataset = pq.ParquetDataset(
        resolver.parsed_dataset_url().path,
        filesystem=resolver.filesystem(),
        validate_schema=False)

    _generate_num_row_groups_per_file_metadata(dataset, spark_context)
    _generate_unischema_metadata(dataset, schema)


def _generate_num_row_groups_per_file_metadata(dataset, spark_context):
    """
    Generates the metadata file containing the number of row groups in each file
    for the parquet dataset located at the dataset_url. It does this in spark by
    opening all parquet files in the dataset on the executors and collecting the
    number of row groups in each file back on the driver.

    :param dataset_url: string url for the parquet dataset. Needs to be a directory.
    :param spark_context: spark context to use for retrieving the number of row groups
    in each parquet file in parallel
    :return: None, upon successful completion the metadata file will exist.
    """
    if not isinstance(dataset.paths, str):
        raise ValueError('Expected dataset.paths to be a single path, not a list of paths')

    # Get the common prefix of all the base path in order to retrieve a relative path
    paths = [piece.path for piece in dataset.pieces]

    # Needed pieces from the dataset must be extracted for spark because the dataset object is not serializable
    fs = dataset.fs
    base_path = dataset.paths
    row_groups = spark_context.parallelize(paths, len(paths)) \
        .map(lambda path: (os.path.relpath(path, base_path), pq.read_metadata(fs.open(path)).num_row_groups)) \
        .collect()
    num_row_groups_str = json.dumps(dict(row_groups))
    # Add the dict for the number of row groups in each file to the parquet file metadata footer
    utils.add_to_dataset_metadata(dataset, ROW_GROUPS_PER_FILE_KEY, num_row_groups_str)


def _generate_unischema_metadata(dataset, schema):
    """
    Generates the serialized unischema and adds it to the dataset parquet metadata to be used upon reading.
    :param dataset: (ParquetDataset) Dataset to attach schema
    :param schema:  (Unischema) Schema to attach to dataset
    :return: None
    """
    # TODO(robbieg): Simply pickling unischema will break if the UnischemaField class is changed,
    #  or the codec classes are changed. We likely need something more robust.
    serialized_schema = pickle.dumps(schema)
    utils.add_to_dataset_metadata(dataset, UNISCHEMA_KEY, serialized_schema)


def load_rowgroup_split(dataset):
    """
    Load dataset row group pieces from metadata
    :param dataset: parquet dataset object.
    :return: splitted pieces, one piece per row group
    """
    # Split the dataset pieces by row group using the precomputed index
    if not dataset.common_metadata:
        raise ValueError('Could not find _metadata file. add_dataset_metadata(..) in'
                         ' dataset_toolkit.etl.dataset_metadata.py should be used to'
                         ' generate this file in your ETL code.'
                         ' You can generate it on an existing dataset using metadata_index_run.py')

    dataset_metadata_dict = dataset.common_metadata.metadata

    use_absolute_paths = False
    if ROW_GROUPS_PER_FILE_KEY not in dataset_metadata_dict:
        # We also need to check for using absolute paths for backwards compatibility with older generated metadata
        use_absolute_paths = True
        if ROW_GROUPS_PER_FILE_KEY_ABSOLUTE_PATHS not in dataset_metadata_dict:
            raise ValueError('Could not find the row groups per file in the dataset metadata file.'
                             ' Metadata file might not be generated properly.'
                             ' Make sure to use add_dataset_metadata(..) in'
                             ' dataset_toolkit.etl.dataset_metadata.py to'
                             ' properly generate this file in your ETL code.'
                             ' You can generate it on an existing dataset using metadata_index_run.py')
    if use_absolute_paths:
        metadata_dict_key = ROW_GROUPS_PER_FILE_KEY_ABSOLUTE_PATHS
    else:
        metadata_dict_key = ROW_GROUPS_PER_FILE_KEY
    row_groups_per_file = json.loads(dataset_metadata_dict[metadata_dict_key])

    split_pieces = []
    # Force order of pieces. The order is not deterministic since it depends on multithreaded directory
    # listing implementation inside pyarrow. We stabilize order here, this way we get reproducable order
    # when pieces shuffling is off. This also enables implementing piece shuffling given a seed
    sorted_pieces = sorted(dataset.pieces, key=attrgetter('path'))
    for piece in sorted_pieces:
        # If we are not using absolute paths, we need to convert the path to a relative path for
        # looking up the number of row groups.
        row_groups_key = piece.path if use_absolute_paths else os.path.relpath(piece.path, dataset.paths)
        for row_group in range(row_groups_per_file[row_groups_key]):
            split_pieces.append(pq.ParquetDatasetPiece(piece.path, row_group, piece.partition_keys))
    return split_pieces


def get_schema(dataset):
    """
    Retrieve schema object stored as part of dataset methadata
    :param dataset:
    :return: unischema object
    """
    # Split the dataset pieces by row group using the precomputed index
    if not dataset.common_metadata:
        raise ValueError('Could not find _metadata file. add_dataset_metadata(..) in'
                         ' dataset_toolkit.etl.dataset_metadata.py should be used to'
                         ' generate this file in your ETL code.'
                         ' You can generate it on an existing dataset using metadata_index_run.py')

    dataset_metadata_dict = dataset.common_metadata.metadata

    # Read schema
    if UNISCHEMA_KEY not in dataset_metadata_dict:
        raise ValueError('Could not find the unischema in the dataset metadata file.'
                         ' Please provide or generate dataset with the unischema attached.'
                         ' Metadata file might not be generated properly.'
                         ' Make sure to use add_dataset_metadata(..) in'
                         ' dataset_toolkit.etl.dataset_metadata.py to'
                         ' properly generate this file in your ETL code.'
                         ' You can generate it on an existing dataset using metadata_index_run.py')
    ser_schema = dataset_metadata_dict[UNISCHEMA_KEY]
    # Since we have moved the unischema class from av.experimental.deepdrive.dataset_toolkit to dataset_toolkit
    # unpickling old schemas will not work. In this case we override the old import path to get backwards compatibility
    try:
        schema = pickle.loads(ser_schema)
    except ImportError:
        import dataset_toolkit
        sys.modules['av.experimental.deepdrive.dataset_toolkit'] = dataset_toolkit
        schema = pickle.loads(ser_schema)
    return schema
