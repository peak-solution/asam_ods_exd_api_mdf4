# Prepare python to use GRPC interface:
# python -m grpc_tools.protoc --proto_path=proto_src --pyi_out=. --python_out=. --grpc_python_out=. ods.proto ods_external_data.proto
import sys, os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import logging
import pathlib
import unittest
from glob import glob

# pylint: disable=E1101
import ods_pb2 as ods
import ods_external_data_pb2 as oed

from external_data_reader import ExternalDataReader


class TestExampleFiles(unittest.TestCase):
    log = logging.getLogger(__name__)

    def __load_structure(self, example_file_uri):
        service = ExternalDataReader()
        handle = service.Open(oed.Identifier(url=example_file_uri, parameters=""), None)
        try:
            structure = service.GetStructure(oed.StructureRequest(handle=handle), None)
            return structure
        finally:
            service.Close(handle, None)

    def test_files(self):
        """test loops over all files and checks if values do match info in structure"""
        example_files_folder = pathlib.Path.joinpath(pathlib.Path(__file__).parent.resolve(), "..", "data", "examples")
        example_files = [y for x in os.walk(example_files_folder) for y in glob(os.path.join(x[0], "*.mf4"))]

        failed = False
        for example_file in example_files:
            example_file_uri = pathlib.Path(example_file).absolute().resolve().as_uri()
            print(f"URI: {example_file_uri}")
            try:
                self.log.info("Retrieve structure")
                structure = self.__load_structure(example_file_uri)
                self.assertNotEqual(structure.name, "")
                self.assertNotEqual(structure.identifier.url, "")

                self.log.info("Check bulk load")
                service = ExternalDataReader()
                handle = service.Open(oed.Identifier(url=example_file_uri, parameters=""), None)
                try:
                    for group in structure.groups:
                        channel_ids = []
                        for channel in group.channels:
                            channel_ids.append(channel.id)
                        values = service.GetValues(
                            oed.ValuesRequest(
                                handle=handle,
                                group_id=group.id,
                                start=0,
                                limit=group.number_of_rows + 10,
                                channel_ids=channel_ids,
                            ),
                            None,
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
                    service.Close(handle, None)
            except Exception as e:
                print(f"FAILED: {e}")
                failed = True

        self.assertFalse(failed, "At least one file failed")


if __name__ == "__main__":
    unittest.main()
