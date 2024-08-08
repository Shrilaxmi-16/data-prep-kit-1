import pathlib
from typing import Any, Union

import pyarrow as pa
from data_processing.transform import AbstractBinaryTransform, AbstractTableTransform


name = "pipeline"
cli_prefix = f"{name}_"
transform_key = "transforms"


class PipelinedTransform(AbstractBinaryTransform):
    """
    Enables the sequencing of transforms.
    Configuration is done by providing a list of configured AbstractBinaryTransform instances under  the "transforms"
    key in the dictionary provided to the initializer.
    Features/considerations include:
        * Transforms must be sequenced such that the output of a given transform, identified by the extension produced,
            must be compatible with the next transform in the sequence.
        * Intermediate input file names are only informative and do not actually exist on disk. The file extensions
            used are those produced by the output of the previous transform.  The base names are constructed
            from the name of the generating transform class name, but should not be relied on.
        * If a transform produces multiple outputs (must be with the same extension) each output is applied through
            the subsequent transforms in the pipeline.
    Restrictions include:
        * metadata produced is merged across all transforms, for any given call to transform/flush_binary() methods.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Create the pipeline using a list of initialize transforms
        Args:
            config:  dictionary holding the following keys
                transforms : a list of AbstractBinaryTransform instances.  All transforms must expect and produce
                the same data type (within the binary array) represented by the file extensions passed into and
                returned by the transform/flush_binary() methods.
        """
        super().__init__(config)
        self.input_extension = None
        self.transforms = config.get(transform_key, None)
        if self.transforms is None:
            raise ValueError(f"Missing configuration key {transform_key} specifying the list of transforms to run")
        for transform in self.transforms:
            if not isinstance(transform, AbstractBinaryTransform):
                raise ValueError(f"{transform} is not an instance of AbstractBinaryTransform")

    def transform_binary(self, file_name: str, byte_array: bytes) -> tuple[list[tuple[bytes, str]], dict[str, Any]]:
        """
        Applies the list of transforms, provided to the initializer, to the input data.
        If a transform produces multiple byte arrays, each will be applied through the downstream transforms.
        Args:
            file_name:
            byte_array:
        Returns:

        """
        r_bytes, r_metadata = self._apply_transforms_to_datum(self.transforms, (file_name, byte_array))
        return r_bytes, r_metadata

    def transform(self, table: pa.Table, file_name: str = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Applies the list of transforms, provided to the initializer, to the input data.
        If a transform produces multiple byte arrays, each will be applied through the downstream transforms.
        Args:
            file_name:
            byte_array:
        Returns:

        """
        r_bytes, r_metadata = self._apply_transforms_to_datum(self.transforms, (file_name, table))
        tables = self._get_table_list(r_bytes)
        return tables, r_metadata

    def _get_table_list(self, transformed: list[tuple[pa.Table, str]]):
        tables = []
        for t in transformed:
            tables.append(t[0])
        return tables

    def _apply_transforms_to_data(
        self, transforms: list[AbstractBinaryTransform], data: list[tuple[str, bytearray]]
    ) -> tuple[list[tuple[bytes, str]], dict[str, Any]]:
        r_bytes = []
        r_metadata = {}
        for datum in data:
            processed, metadata = self._apply_transforms_to_datum(transforms, data)
            r_bytes.extend(processed)
            r_metadata = r_metadata | metadata

        return r_bytes, r_metadata

    def _apply_transforms_to_datum(
        self,
        transforms: Union[list[AbstractBinaryTransform], list[AbstractTableTransform]],
        datum: Union[tuple[str, bytearray], tuple[str, pa.Table]],
    ) -> tuple[list[tuple[bytes, str]], dict[str, Any]]:
        """
        Apply the list of transforms to the given datum tuple of filename and byte[]
        Args:
            transforms:
            datum:
        Returns: same as transform_binary().

        """
        r_metadata = {}
        pending_to_process = [(datum[0], datum[1])]
        for transform in transforms:
            transform_name = type(transform).__name__
            to_process = pending_to_process
            pending_to_process = []
            for tp in to_process:  # Over all outputs from the last transform  (or the initial input)
                fname = tp[0]
                to_transform = tp[1]
                transformation_tuples, metadata = self._call_transform(transform, to_transform, fname)
                # Capture the list of outputs from this transform as inputs to the next (or as the return values).
                for transformation in transformation_tuples:
                    transformed, extension = transformation
                    fname = transform_name + "-output" + extension
                    next = (fname, transformed)
                    pending_to_process.append(next)
                # TODO: this is not quite right and might overwrite previous values.
                # Would be better if we could somehow support lists.
                r_metadata = r_metadata | metadata

        # Strip the pseudo-base filename from the pending_to_process tuples, leaving only the extension, as required.
        r_bytes = []
        for tp in pending_to_process:
            fname = tp[0]
            byte_array = tp[1]
            extension = pathlib.Path(fname).suffix
            tp = (byte_array, extension)
            r_bytes.append(tp)

        return r_bytes, r_metadata

    def _call_transform(
        self,
        transform: Union[AbstractTableTransform, AbstractBinaryTransform],
        datum: Union[pa.Table, bytearray],
        file_name: str,
    ):
        is_table_transform = isinstance(datum, pa.Table)
        if is_table_transform:
            tables, metadata = transform.transform(datum, file_name)
            transformation_tuples = []
            for table in tables:
                transformation_tuples.append((table, ".parquet"))
        else:
            transformation_tuples, metadata = transform.transform_binary(file_name, datum)
        return transformation_tuples, metadata

    def _call_flush(self, transform: Union[AbstractTableTransform, AbstractBinaryTransform]):
        is_table_transform = isinstance(transform, AbstractTableTransform)
        if is_table_transform:
            tables, metadata = transform.flush()
            transformation_tuples = []
            for table in tables:
                transformation_tuples.append((table, ".parquet"))
        else:
            transformation_tuples, metadata = transform.flush_binary()
        return transformation_tuples, metadata

    def flush_binary(self) -> tuple[list[tuple[bytes, str]], dict[str, Any]]:
        return self._flush_transforms()

    def flush(self) -> tuple[list[pa.Table], dict[str, Any]]:
        transformed, metadata = self._flush_transforms()
        # but only return the table list and not the extensions as is done for flush_binary()
        tables = self._get_table_list(transformed)

    def _flush_transforms(self) -> tuple[list[Union[tuple[bytes, str], tuple[pa.Table, str]]], dict[str, Any]]:
        """
        Call flush on all transforms in the pipeline passing flushed results to downstream
        transforms, as appropriate.  Aggregated results.
        Returns:

        """

        r_bytes = []
        r_metadata = {}
        index = 0
        for transform in self.transforms:  # flush each transform
            index += 1
            transformation_tuples, metadata = self._call_flush(transform)
            r_metadata = r_metadata | metadata
            if len(transformation_tuples) > 0:  # Something was flushed from this transform.
                downstream_transforms = self.transforms[index:]
                if len(downstream_transforms) > 0:
                    # Apply the flushed results to the downstream transforms.
                    transformation_tuples, metadata = self._apply_transforms_to_data(
                        downstream_transforms, transformation_tuples
                    )
                    r_bytes.extend(transformation_tuples)
                    # TODO: this is not quite right and might overwrite previous values.
                    # Would be better if we could somehow support lists.
                    r_metadata = r_metadata | metadata
                else:
                    # We flushed the last transform so just append its results.
                    r_bytes.extend(transformation_tuples)

        return r_bytes, r_metadata
