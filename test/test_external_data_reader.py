from datetime import datetime
import os
import tempfile
import unittest
from pathlib import Path
import grpc
from google.protobuf.json_format import MessageToJson

from test.mock_servicer_context import MockServicerContext
from asammdf import MDF
from external_data_reader import ExternalDataReader
import ods_external_data_pb2 as exd_api


# pylint: disable=E1101


class TestExternalDataReader(unittest.TestCase):

    def setUp(self):
        self.service = ExternalDataReader()
        self.mock_context = MockServicerContext()

    def test_open_existing_file(self):
        # Create a temporary MDF file
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.mf4")
            with MDF(version="4.10", file_comment="test.mf4") as mdf4:
                mdf4.start_time = datetime.now()
                mdf4.save(file_path, compression=2, overwrite=True)

            identifier = exd_api.Identifier(
                url=Path(file_path).resolve().as_uri(), parameters="")
            handle = self.service.Open(identifier, None)
            self.assertIsNotNone(handle.uuid)

    def test_open_non_existing_file(self):
        identifier = exd_api.Identifier(
            url="file:///non_existing_file.mf4", parameters="")
        with self.assertRaises(grpc.RpcError) as _:
            self.service.Open(identifier, self.mock_context)

        self.assertEqual(self.mock_context.code(), grpc.StatusCode.NOT_FOUND)

    def test_simple_example(self):
        main_file_path = Path.joinpath(
            Path(__file__).parent.resolve(), "..", "data", "simple.mf4")

        main_file_url = Path(main_file_path).absolute().resolve().as_uri()

        main_external_data_reader = ExternalDataReader()

        main_exd_api_handle = main_external_data_reader.Open(
            exd_api.Identifier(url=main_file_url, parameters=""),
            None
        )
        try:

            main_exd_api_structure = main_external_data_reader.GetStructure(
                exd_api.StructureRequest(handle=main_exd_api_handle), None)
            print(MessageToJson(main_exd_api_structure))

            print(
                MessageToJson(
                    main_external_data_reader.GetValues(
                        exd_api.ValuesRequest(
                            handle=main_exd_api_handle, group_id=0, channel_ids=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], start=0, limit=10
                        ),
                        None,
                    )
                )
            )
        finally:
            main_external_data_reader.Close(main_exd_api_handle, None)

    def test_close_mdf(self):
        # Create a temporary MDF file
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.mf4")
            with MDF(version="4.10", file_comment="test.mf4") as mdf4:
                mdf4.start_time = datetime.now()
                mdf4.save(file_path, compression=2, overwrite=True)

            identifier = exd_api.Identifier(
                url=Path(file_path).resolve().as_uri(), parameters="")
            handle1 = self.service.Open(identifier, None)
            self.assertIsNotNone(handle1.uuid)

            handle2 = self.service.Open(identifier, None)
            self.assertIsNotNone(handle2.uuid)

            self.assertNotEqual(handle1.uuid, handle2.uuid)

            # Close the MDF file
            self.service.Close(handle1, None)
            self.service.Close(handle2, None)
