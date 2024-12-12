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

            identifier = exd_api.Identifier(url=Path(file_path).resolve().as_uri(), parameters="")
            try:
                handle = self.service.Open(identifier, None)
                self.assertIsNotNone(handle.uuid)
            finally:
                self.service.Close(handle, None)

    def test_open_non_existing_file(self):
        identifier = exd_api.Identifier(url="file:///non_existing_file.mf4", parameters="")
        with self.assertRaises(grpc.RpcError) as _:
            self.service.Open(identifier, self.mock_context)

        self.assertEqual(self.mock_context.code(), grpc.StatusCode.NOT_FOUND)

    def test_simple_example(self):
        main_file_path = Path.joinpath(Path(__file__).parent.resolve(), "..", "data", "simple.mf4")

        main_file_url = Path(main_file_path).absolute().resolve().as_uri()

        main_external_data_reader = ExternalDataReader()

        main_exd_api_handle = main_external_data_reader.Open(
            exd_api.Identifier(url=main_file_url, parameters=""), None
        )
        try:

            main_exd_api_structure = main_external_data_reader.GetStructure(
                exd_api.StructureRequest(handle=main_exd_api_handle), None
            )
            print(MessageToJson(main_exd_api_structure))

            print(
                MessageToJson(
                    main_external_data_reader.GetValues(
                        exd_api.ValuesRequest(
                            handle=main_exd_api_handle,
                            group_id=0,
                            channel_ids=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                            start=0,
                            limit=10,
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

            identifier = exd_api.Identifier(url=Path(file_path).resolve().as_uri(), parameters="")
            handle1 = self.service.Open(identifier, None)
            self.assertIsNotNone(handle1.uuid)

            handle2 = self.service.Open(identifier, None)
            self.assertIsNotNone(handle2.uuid)

            self.assertNotEqual(handle1.uuid, handle2.uuid)

            # Close the MDF file
            self.service.Close(handle1, None)
            self.service.Close(handle2, None)

    def test_mdf_file_meta(self):
        start_time = datetime(2021, 1, 1, 0, 0, 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "meta.mf4")
            with MDF(version="4.10", file_comment="my_file_comment") as mdf4:
                mdf4.start_time = start_time
                mdf4.header.description = "my_comment"
                mdf4.header.author = "my_author"
                mdf4.header.department = "my_department"
                mdf4.header.project = "my_project"
                mdf4.header.subject = "my_subject"
                mdf4.save(file_path, compression=2, overwrite=True)

            identifier = exd_api.Identifier(url=Path(file_path).resolve().as_uri(), parameters="")
            handle1 = self.service.Open(identifier, None)
            try:
                file_content = self.service.GetStructure(exd_api.StructureRequest(handle=handle1), None)
                file_attributes = file_content.attributes.variables

                attribute = file_attributes.get("start_time")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "20210101000000000000")

                attribute = file_attributes.get("description")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_comment")

                attribute = file_attributes.get("author")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_author")

                attribute = file_attributes.get("department")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_department")

                attribute = file_attributes.get("project")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_project")

                attribute = file_attributes.get("subject")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_subject")

            finally:
                self.service.Close(handle1, None)

    def test_mdf_file_meta_tree(self):
        start_time = datetime(2021, 1, 1, 0, 0, 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "meta.mf4")
            with MDF(version="4.10", file_comment="my_file_comment") as mdf4:
                mdf4.start_time = start_time
                mdf4.header.comment = """<HDcomment>
    <TX>my_description</TX>
    <common_properties>
        <e name="prop1">my_prop1</e>
        <tree name="abc">
            <e name="def1">my_def1</e>
            <e name="def2">my_def2</e>
            <e name="def3">my_def3</e>
        </tree>
        <e name="prop2">my_prop2</e>
    </common_properties>
</HDcomment>"""
                mdf4.save(file_path, compression=2, overwrite=True)

            identifier = exd_api.Identifier(url=Path(file_path).resolve().as_uri(), parameters="")
            handle1 = self.service.Open(identifier, None)
            try:
                file_content = self.service.GetStructure(exd_api.StructureRequest(handle=handle1), None)
                file_attributes = file_content.attributes.variables

                attribute = file_attributes.get("start_time")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "20210101000000000000")

                attribute = file_attributes.get("description")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_description")

                attribute = file_attributes.get("prop1")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_prop1")

                attribute = file_attributes.get("prop2")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_prop2")

                attribute = file_attributes.get("abc~def1")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_def1")

                attribute = file_attributes.get("abc~def2")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_def2")

                attribute = file_attributes.get("abc~def3")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "my_def3")

            finally:
                self.service.Close(handle1, None)

    def test_measurement_begin(self):
        main_file_path = Path.joinpath(Path(__file__).parent.resolve(), "..", "data", "simple.mf4")

        main_file_url = Path(main_file_path).absolute().resolve().as_uri()

        main_external_data_reader = ExternalDataReader()

        main_exd_api_handle = main_external_data_reader.Open(
            exd_api.Identifier(url=main_file_url, parameters=""), None
        )
        try:

            file_content = main_external_data_reader.GetStructure(
                exd_api.StructureRequest(handle=main_exd_api_handle), None
            )

            attribute = file_content.attributes.variables.get("start_time")
            self.assertIsNotNone(attribute)
            self.assertEqual(attribute.string_array.values[0], "20230606202225335777")

            for group in file_content.groups:
                attribute = group.attributes.variables.get("measurement_begin")
                self.assertIsNotNone(attribute)
                self.assertEqual(attribute.string_array.values[0], "20230606202225335777")
        finally:
            main_external_data_reader.Close(main_exd_api_handle, None)
