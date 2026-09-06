import logging
import os
import pathlib
import unittest
from glob import glob

from ods_exd_api_box import ExternalDataReader, FileHandlerRegistry, exd_api, ods

from asam_ods_exd_api_mdf4 import ExternalDataFile
from tests.mock_servicer_context import MockServicerContext

# pylint: disable=E1101


class TestExampleFiles(unittest.TestCase):
    log = logging.getLogger(__name__)

    def setUp(self):
        """Register ExternalDataFile handler before each test."""
        FileHandlerRegistry.register(file_type_name="test", factory=ExternalDataFile)
        self.mock_context = MockServicerContext()

    def __load_structure(self, example_file_uri: str):
        service = ExternalDataReader()
        handle = service.Open(exd_api.Identifier(url=example_file_uri, parameters=""), self.mock_context)
        try:
            structure = service.GetStructure(exd_api.StructureRequest(handle=handle), self.mock_context)
            return structure
        finally:
            service.Close(handle, self.mock_context)

    def __is_independent_channel(self, channel: exd_api.StructureResult.Channel) -> bool:
        if not channel.attributes:
            return False
        if not channel.attributes.variables:
            return False
        independent_attr: ods.ContextVariables.ContextVariableValue | None = channel.attributes.variables.get(
            "independent"
        )
        if not independent_attr:
            return False

        assert independent_attr.HasField("long_array"), "Independent attribute should be a long_array"
        return independent_attr.long_array.values[0] == 1

    def test_files(self):
        """Parameterized test over all example files using unittest subTest."""
        example_files_folder = pathlib.Path.joinpath(pathlib.Path(__file__).parent.resolve(), "..", "data", "examples")
        example_files = [y for x in os.walk(example_files_folder) for y in glob(os.path.join(x[0], "*.mf4"))]
        self.assertGreater(len(example_files), 0, "No .mf4 example files found")

        for example_file in example_files:
            example_file_path = pathlib.Path(example_file)
            example_file_uri = example_file_path.absolute().resolve().as_uri()
            relative_example_file = example_file_path.relative_to(example_files_folder)
            with self.subTest(example_file=str(relative_example_file)):
                self.__check_file_including_bulk(example_file_uri)

    def test_file(self):
        """Check a single file"""
        example_file = pathlib.Path.joinpath(pathlib.Path(__file__).parent.resolve(), "..", "data", "simple.mf4")
        assert example_file.exists()
        example_file_uri = pathlib.Path(example_file).absolute().resolve().as_uri()
        self.__check_file_including_bulk(example_file_uri)

    def __check_file_including_bulk(self, example_file_uri: str):
        print(f"URI: {example_file_uri}")
        self.log.info("Retrieve structure")
        structure = self.__load_structure(example_file_uri)
        self.assertNotEqual(structure.name, "")
        self.assertNotEqual(structure.identifier.url, "")

        self.log.info("Check bulk load")
        service = ExternalDataReader()
        handle = service.Open(exd_api.Identifier(url=example_file_uri, parameters=""), self.mock_context)
        try:
            for group in structure.groups:
                channel_ids: list[int] = []
                independent_count = 0
                for channel in group.channels:
                    channel_ids.append(channel.id)
                    if self.__is_independent_channel(channel):
                        independent_count += 1
                self.assertLessEqual(independent_count, 1, f"Group {group.name} has more than one independent channel")

                values = service.GetValues(
                    exd_api.ValuesRequest(
                        handle=handle,
                        group_id=group.id,
                        start=0,
                        limit=group.number_of_rows + 10,
                        channel_ids=channel_ids,
                    ),
                    self.mock_context,
                )
                for values_channel_index, values_channel in enumerate(values.channels):
                    structure_channel = group.channels[values_channel_index]
                    self.assertEqual(values_channel.id, structure_channel.id)
                    self.assertEqual(values_channel.values.data_type, structure_channel.data_type)
                    if ods.DataTypeEnum.DT_COMPLEX == values_channel.values.data_type:
                        vals = values_channel.values.float_array.values
                        self.assertEqual(len(vals), group.number_of_rows * 2)
                    elif ods.DataTypeEnum.DT_DCOMPLEX == values_channel.values.data_type:
                        vals = values_channel.values.double_array.values
                        self.assertEqual(len(vals), group.number_of_rows * 2)
                    elif ods.DataTypeEnum.DT_BYTE == values_channel.values.data_type:
                        vals = values_channel.values.byte_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_SHORT == values_channel.values.data_type:
                        vals = values_channel.values.long_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_LONG == values_channel.values.data_type:
                        vals = values_channel.values.long_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_LONGLONG == values_channel.values.data_type:
                        vals = values_channel.values.longlong_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_FLOAT == values_channel.values.data_type:
                        vals = values_channel.values.float_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_DOUBLE == values_channel.values.data_type:
                        vals = values_channel.values.double_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_STRING == values_channel.values.data_type:
                        vals = values_channel.values.string_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_DATE == values_channel.values.data_type:
                        vals = values_channel.values.string_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_BYTESTR == values_channel.values.data_type:
                        vals = values_channel.values.bytestr_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    elif ods.DataTypeEnum.DT_BOOLEAN == values_channel.values.data_type:
                        vals = values_channel.values.boolean_array.values
                        self.assertEqual(len(vals), group.number_of_rows)
                    else:
                        self.assertFalse(True, f"Unknown type {values_channel.values.data_type}")
        finally:
            service.Close(handle, self.mock_context)
