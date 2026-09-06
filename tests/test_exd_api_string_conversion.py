import logging
import pathlib
import unittest

from google.protobuf.json_format import MessageToJson, ParseDict
from ods_exd_api_box import ExternalDataReader, FileHandlerRegistry, exd_api, ods

from asam_ods_exd_api_mdf4 import ExternalDataFile

# pylint: disable=E1101


class TestExdApiStringConversion(unittest.TestCase):
    log = logging.getLogger(__name__)

    def setUp(self):
        """Register ExternalDataFile handler before each test."""
        FileHandlerRegistry.register(file_type_name="test", factory=ExternalDataFile)

    def _get_example_file_uri(self, file_name):
        example_file_path = pathlib.Path.joinpath(
            pathlib.Path(__file__).parent.resolve(), "..", "data", "examples", file_name
        )
        rv = pathlib.Path(example_file_path).absolute().resolve()
        assert rv.exists()
        return rv.as_uri()

    def test(self):
        file_uri = self._get_example_file_uri("mdf4_demo_no_arrays.mf4")

        service = ExternalDataReader()
        handle = service.Open(exd_api.Identifier(url=file_uri, parameters=""), None)
        try:
            structure = service.GetStructure(exd_api.StructureRequest(handle=handle), None)
            data_types = [ch.data_type for ch in structure.groups[0].channels]
            assert [
                ods.DT_DOUBLE,
                ods.DT_DOUBLE,
                ods.DT_DOUBLE,
                ods.DT_DOUBLE,
                ods.DT_DOUBLE,
                ods.DT_STRING,
                ods.DT_BYTESTR,
                ods.DT_DOUBLE,
                ods.DT_STRING,
                ods.DT_DOUBLE,
                ods.DT_STRING,
            ] == data_types
            self.log.info("Names: %s", [ch.name for ch in structure.groups[0].channels])
            self.log.info("Data types: %s", [ods.DataTypeEnum.Name(dt) for dt in data_types])

            values = service.GetValues(
                exd_api.ValuesRequest(
                    handle=handle,
                    group_id=structure.groups[0].id,
                    channel_ids=[ch.id for ch in structure.groups[0].channels],
                    start=0,
                    limit=10,
                ),
                None,
            )
            self.log.info("Values: %s", MessageToJson(values))

            values_ref = ParseDict(
                {
                    "channels": [
                        {
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {"values": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]},
                            }
                        },
                        {
                            "id": "1",
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {"values": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]},
                            },
                        },
                        {
                            "id": "2",
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {"values": [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5]},
                            },
                        },
                        {
                            "id": "3",
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {
                                    "values": [
                                        0.0,
                                        0.01999966666833333,
                                        0.03999733338666616,
                                        0.05999100040499132,
                                        0.07997866837326832,
                                        0.09995833854135666,
                                        0.11992801295888919,
                                        0.13988569467506554,
                                        0.1598293879383454,
                                        0.17975709839602208,
                                    ]
                                },
                            },
                        },
                        {
                            "id": "4",
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {"values": [3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5]},
                            },
                        },
                        {
                            "id": "5",
                            "values": {
                                "dataType": "DT_STRING",
                                "stringArray": {
                                    "values": [
                                        "String channel sample 0",
                                        "String channel sample 1",
                                        "String channel sample 2",
                                        "String channel sample 3",
                                        "String channel sample 4",
                                        "String channel sample 5",
                                        "String channel sample 6",
                                        "String channel sample 7",
                                        "String channel sample 8",
                                        "String channel sample 9",
                                    ]
                                },
                            },
                        },
                        {
                            "id": "6",
                            "values": {
                                "dataType": "DT_BYTESTR",
                                "bytestrArray": {
                                    "values": [
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                        "b29vb29vb28=",
                                    ]
                                },
                            },
                        },
                        {
                            "id": "7",
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {"values": [0.0, -1.0, -2.0, -3.0, -4.0, -5.0, -6.0, -7.0, -8.0, -9.0]},
                            },
                        },
                        {
                            "id": "8",
                            "values": {
                                "dataType": "DT_STRING",
                                "stringArray": {
                                    "values": [
                                        "key_0",
                                        "key_1",
                                        "key_2",
                                        "key_3",
                                        "key_4",
                                        "key_5",
                                        "key_6",
                                        "key_7",
                                        "key_8",
                                        "key_9",
                                    ]
                                },
                            },
                        },
                        {
                            "id": "9",
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {"values": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]},
                            },
                        },
                        {
                            "id": "10",
                            "values": {
                                "dataType": "DT_STRING",
                                "stringArray": {
                                    "values": [
                                        "Level 0",
                                        "Level 0",
                                        "Level 1",
                                        "Level 1",
                                        "Level 2",
                                        "Level 2",
                                        "Level 3",
                                        "Level 4",
                                        "Level 4",
                                        "Level 5",
                                    ]
                                },
                            },
                        },
                    ]
                },
                exd_api.ValuesResult(),
            )

            assert values == values_ref

        finally:
            service.Close(handle, None)

    def test_partial(self):
        file_uri = self._get_example_file_uri("PartialConversionValueRange2TextRational.mf4")

        service = ExternalDataReader()
        handle = service.Open(exd_api.Identifier(url=file_uri, parameters=""), None)
        try:
            structure = service.GetStructure(exd_api.StructureRequest(handle=handle), None)
            data_types = [ch.data_type for ch in structure.groups[0].channels]
            self.log.info("Names: %s", [ch.name for ch in structure.groups[0].channels])
            self.log.info("Data types: %s", [ods.DataTypeEnum.Name(dt) for dt in data_types])
            assert [ods.DT_STRING, ods.DT_DOUBLE] == data_types

            values = service.GetValues(
                exd_api.ValuesRequest(
                    handle=handle,
                    group_id=structure.groups[0].id,
                    channel_ids=[ch.id for ch in structure.groups[0].channels],
                    start=80,
                    limit=10,
                ),
                None,
            )
            self.log.info("Values: %s", MessageToJson(values))

            values_ref = ParseDict(
                {
                    "channels": [
                        {
                            "values": {
                                "dataType": "DT_STRING",
                                "stringArray": {
                                    "values": [
                                        "-1.4000000000000146",
                                        "-1.2800000000000153",
                                        "-1.1600000000000161",
                                        "-1.0400000000000151",
                                        "nan",
                                        "nan",
                                        "nan",
                                        "nan",
                                        "nan",
                                        "nan",
                                    ]
                                },
                            }
                        },
                        {
                            "id": "1",
                            "values": {
                                "dataType": "DT_DOUBLE",
                                "doubleArray": {
                                    "values": [
                                        7.999999999999988,
                                        8.099999999999987,
                                        8.199999999999987,
                                        8.299999999999986,
                                        8.399999999999986,
                                        8.499999999999986,
                                        8.599999999999985,
                                        8.699999999999985,
                                        8.799999999999985,
                                        8.899999999999984,
                                    ]
                                },
                            },
                        },
                    ]
                },
                exd_api.ValuesResult(),
            )

            assert values == values_ref

        finally:
            service.Close(handle, None)
