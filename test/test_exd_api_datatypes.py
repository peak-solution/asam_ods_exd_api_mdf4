# Prepare python to use GRPC interface:
# python -m grpc_tools.protoc --proto_path=proto_src --pyi_out=. --python_out=. --grpc_python_out=. ods.proto ods_external_data.proto
import sys, os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import logging
import pathlib
import unittest
from datetime import datetime
import tempfile
from pathlib import Path

import numpy as np

import ods_pb2 as ods
import ods_external_data_pb2 as oed

# pylint: disable=E1101
from external_data_reader import ExternalDataReader
from google.protobuf.json_format import MessageToJson

from asammdf import MDF, Signal


class TestDataTypes(unittest.TestCase):
    log = logging.getLogger(__name__)

    def _get_example_file_path(self, file_name):
        example_file_path = pathlib.Path.joinpath(pathlib.Path(__file__).parent.resolve(), "..", "data", file_name)
        return pathlib.Path(example_file_path).absolute().resolve().as_uri()

    def test_data_type(self):
        with tempfile.TemporaryDirectory() as temporary_directory_name:
            file_path = os.path.join(temporary_directory_name, "all_datatypes_test.mf4")

            with MDF(version="4.10", file_comment="all_datatypes_test.mf4") as mdf4:
                mdf4.start_time = datetime.now()

                timestamps = [0, 1]

                sigs = []
                sigs.append(
                    Signal(
                        samples=np.array([1 + 2j, 3 + 4j], np.complex64),
                        timestamps=timestamps,
                        comment="complex64 data",
                        name="complex64_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([5 + 6j, 7 + 8j], np.complex128),
                        timestamps=timestamps,
                        comment="complex128 data",
                        name="complex128_data",
                        unit="ns",
                    )
                )
                mdf4.append(sigs, comment="group_complex", common_timebase=True)

                sigs = []
                sigs.append(
                    Signal(
                        samples=np.array([-2, 4], np.int8),
                        timestamps=timestamps,
                        comment="int8 data",
                        name="int8_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([2, 4], np.uint8),
                        timestamps=timestamps,
                        comment="uint8 data",
                        name="uint8_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([-2, 4], np.int16),
                        timestamps=timestamps,
                        comment="int16 data",
                        name="int16_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([2, 4], np.uint16),
                        timestamps=timestamps,
                        comment="uint16 data",
                        name="uint16_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([-2, 4], np.int32),
                        timestamps=timestamps,
                        comment="int32 data",
                        name="int32_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([2, 4], np.uint32),
                        timestamps=timestamps,
                        comment="uint32 data",
                        name="uint32_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([-2, 4], np.int64),
                        timestamps=timestamps,
                        comment="int64 data",
                        name="int64_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([2, 4], np.uint64),
                        timestamps=timestamps,
                        comment="uint64 data",
                        name="uint64_data",
                        unit="ns",
                    )
                )
                mdf4.append(sigs, comment="group_int", common_timebase=True)

                sigs = []
                sigs.append(
                    Signal(
                        samples=np.array([1.1, 1.2], np.float32),
                        timestamps=timestamps,
                        comment="float32 data",
                        name="float32_data",
                        unit="ns",
                    )
                )
                sigs.append(
                    Signal(
                        samples=np.array([2.1, 2.2], np.float64),
                        timestamps=timestamps,
                        comment="float64 data",
                        name="float64_data",
                        unit="ns",
                    )
                )
                mdf4.append(sigs, comment="group_real", common_timebase=True)

                sigs = []
                sigs.append(
                    Signal(
                        samples=["abc", "def"],
                        timestamps=timestamps,
                        comment="string data",
                        name="string_data",
                        unit="ns",
                        encoding="utf-8",
                    )
                )
                mdf4.append(sigs, comment="group_string", common_timebase=True)

                mdf4.save(file_path, compression=2, overwrite=True)

            service = ExternalDataReader()
            handle = service.Open(oed.Identifier(url=Path(file_path).resolve().as_uri(), parameters=""), None)
            try:
                structure = service.GetStructure(oed.StructureRequest(handle=handle), None)
                self.log.info(MessageToJson(structure))

                self.assertEqual(structure.name, "all_datatypes_test.mf4")
                self.assertEqual(len(structure.groups), 4)
                self.assertEqual(structure.groups[0].number_of_rows, 2)
                self.assertEqual(len(structure.groups[0].channels), 3)
                self.assertEqual(structure.groups[1].number_of_rows, 2)
                self.assertEqual(len(structure.groups[1].channels), 9)
                self.assertEqual(structure.groups[2].number_of_rows, 2)
                self.assertEqual(len(structure.groups[2].channels), 3)
                self.assertEqual(structure.groups[3].number_of_rows, 2)
                self.assertEqual(len(structure.groups[3].channels), 2)

                self.assertEqual(structure.groups[0].channels[1].data_type, ods.DataTypeEnum.DT_COMPLEX)
                self.assertEqual(structure.groups[0].channels[2].data_type, ods.DataTypeEnum.DT_DCOMPLEX)

                self.assertEqual(structure.groups[1].channels[1].data_type, ods.DataTypeEnum.DT_SHORT)
                self.assertEqual(structure.groups[1].channels[2].data_type, ods.DataTypeEnum.DT_BYTE)
                self.assertEqual(structure.groups[1].channels[3].data_type, ods.DataTypeEnum.DT_SHORT)
                self.assertEqual(structure.groups[1].channels[4].data_type, ods.DataTypeEnum.DT_LONG)
                self.assertEqual(structure.groups[1].channels[5].data_type, ods.DataTypeEnum.DT_LONG)
                self.assertEqual(structure.groups[1].channels[6].data_type, ods.DataTypeEnum.DT_LONGLONG)
                self.assertEqual(structure.groups[1].channels[7].data_type, ods.DataTypeEnum.DT_LONGLONG)
                self.assertEqual(structure.groups[1].channels[8].data_type, ods.DataTypeEnum.DT_DOUBLE)

                self.assertEqual(structure.groups[2].channels[1].data_type, ods.DataTypeEnum.DT_FLOAT)
                self.assertEqual(structure.groups[2].channels[2].data_type, ods.DataTypeEnum.DT_DOUBLE)

                self.assertEqual(structure.groups[3].channels[1].data_type, ods.DataTypeEnum.DT_STRING)

                values = service.GetValues(
                    oed.ValuesRequest(handle=handle, group_id=0, start=0, limit=2, channel_ids=[0, 1, 2]), None
                )
                self.assertEqual(values.channels[1].values.data_type, ods.DataTypeEnum.DT_COMPLEX)
                self.assertSequenceEqual(values.channels[1].values.float_array.values, [1.0, 2.0, 3.0, 4.0])
                self.assertEqual(values.channels[2].values.data_type, ods.DataTypeEnum.DT_DCOMPLEX)
                self.assertSequenceEqual(values.channels[2].values.double_array.values, [5.0, 6.0, 7.0, 8.0])

                values = service.GetValues(
                    oed.ValuesRequest(
                        handle=handle, group_id=1, start=0, limit=2, channel_ids=[0, 1, 2, 3, 4, 5, 6, 7, 8]
                    ),
                    None,
                )
                self.assertEqual(values.channels[1].values.data_type, ods.DataTypeEnum.DT_SHORT)
                self.assertSequenceEqual(values.channels[1].values.long_array.values, [-2, 4])
                self.assertEqual(values.channels[2].values.data_type, ods.DataTypeEnum.DT_BYTE)
                self.assertSequenceEqual(values.channels[2].values.byte_array.values, [2, 4])
                self.assertEqual(values.channels[3].values.data_type, ods.DataTypeEnum.DT_SHORT)
                self.assertSequenceEqual(values.channels[3].values.long_array.values, [-2, 4])
                self.assertEqual(values.channels[4].values.data_type, ods.DataTypeEnum.DT_LONG)
                self.assertSequenceEqual(values.channels[4].values.long_array.values, [2, 4])
                self.assertEqual(values.channels[5].values.data_type, ods.DataTypeEnum.DT_LONG)
                self.assertSequenceEqual(values.channels[5].values.long_array.values, [-2, 4])
                self.assertEqual(values.channels[6].values.data_type, ods.DataTypeEnum.DT_LONGLONG)
                self.assertSequenceEqual(values.channels[6].values.longlong_array.values, [2, 4])
                self.assertEqual(values.channels[7].values.data_type, ods.DataTypeEnum.DT_LONGLONG)
                self.assertSequenceEqual(values.channels[7].values.longlong_array.values, [-2, 4])
                self.assertEqual(values.channels[8].values.data_type, ods.DataTypeEnum.DT_DOUBLE)
                self.assertSequenceEqual(values.channels[8].values.double_array.values, [2.0, 4.0])

                values = service.GetValues(
                    oed.ValuesRequest(handle=handle, group_id=2, start=0, limit=2, channel_ids=[0, 1, 2]), None
                )
                self.assertEqual(values.channels[1].values.data_type, ods.DataTypeEnum.DT_FLOAT)
                self.assertSequenceEqual(
                    values.channels[1].values.float_array.values, [1.100000023841858, 1.2000000476837158]
                )
                self.assertEqual(values.channels[2].values.data_type, ods.DataTypeEnum.DT_DOUBLE)
                self.assertSequenceEqual(values.channels[2].values.double_array.values, [2.1, 2.2])

                values = service.GetValues(
                    oed.ValuesRequest(handle=handle, group_id=3, start=0, limit=2, channel_ids=[0, 1]), None
                )
                self.assertEqual(values.channels[1].values.data_type, ods.DataTypeEnum.DT_STRING)
                self.assertSequenceEqual(values.channels[1].values.string_array.values, ["abc", "def"])

            finally:
                service.Close(handle, None)

    def test_independent(self):
        with tempfile.TemporaryDirectory() as temporary_directory_name:
            file_path = os.path.join(temporary_directory_name, "independent_test.mf4")

            with MDF(version="4.10", file_comment="independent_test.mf4") as mdf4:
                mdf4.start_time = datetime.now()

                timestamps = [0, 1]

                sigs = []
                sigs.append(
                    Signal(
                        samples=np.array([2, 4], np.int32),
                        timestamps=timestamps,
                        comment="int32 data",
                        name="int32_data",
                        unit="ns",
                    )
                )
                mdf4.append(sigs, comment="group", common_timebase=True)

                mdf4.save(file_path, compression=2, overwrite=True)

            service = ExternalDataReader()
            handle = service.Open(oed.Identifier(url=Path(file_path).resolve().as_uri(), parameters=""), None)
            try:
                structure = service.GetStructure(oed.StructureRequest(handle=handle), None)
                self.log.info(MessageToJson(structure))
                print(MessageToJson(structure))

                self.assertEqual(structure.name, "independent_test.mf4")
                self.assertEqual(len(structure.groups), 1)
                self.assertEqual(structure.groups[0].number_of_rows, 2)
                self.assertEqual(len(structure.groups[0].channels), 2)

                self.assertEqual("time", structure.groups[0].channels[0].name)
                self.assertEqual("int32_data", structure.groups[0].channels[1].name)

                self.assertEqual(structure.groups[0].channels[0].data_type, ods.DataTypeEnum.DT_DOUBLE)
                self.assertEqual(structure.groups[0].channels[1].data_type, ods.DataTypeEnum.DT_LONG)

                self.assertTrue("independent" in structure.groups[0].channels[0].attributes.variables)
                self.assertEqual(
                    1, structure.groups[0].channels[0].attributes.variables["independent"].long_array.values[0]
                )
                self.assertTrue("independent" not in structure.groups[0].channels[1].attributes.variables)

                self.assertTrue("description" not in structure.groups[0].channels[0].attributes.variables)
                self.assertTrue("description" in structure.groups[0].channels[1].attributes.variables)
                self.assertEqual(
                    "int32 data",
                    structure.groups[0].channels[1].attributes.variables["description"].string_array.values[0],
                )

                values = service.GetValues(
                    oed.ValuesRequest(handle=handle, group_id=0, start=0, limit=2, channel_ids=[0, 1]), None
                )
                self.assertEqual(values.channels[0].values.data_type, ods.DataTypeEnum.DT_DOUBLE)
                self.assertSequenceEqual(values.channels[0].values.double_array.values, [0.0, 1.0])
                self.assertEqual(values.channels[1].values.data_type, ods.DataTypeEnum.DT_LONG)
                self.assertSequenceEqual(values.channels[1].values.long_array.values, [2, 4])
            finally:
                service.Close(handle, None)


if __name__ == "__main__":
    unittest.main()
