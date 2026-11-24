import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import grpc
from asammdf import MDF
from google.protobuf.json_format import MessageToJson
from ods_exd_api_box import ExternalDataReader, FileHandlerRegistry, NotMyFileError, exd_api

from asam_ods_exd_api_mdf4 import ExternalDataFile
from tests.mock_servicer_context import MockServicerContext

# pylint: disable=E1101


class TestExternalDataReader(unittest.TestCase):
    def setUp(self):
        FileHandlerRegistry.register(file_type_name="test", factory=ExternalDataFile)
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

    def test_open_mdf_file_with_dat_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.dat"
            mdf3_path = Path(temp_dir) / "test.mdf"
            with MDF(version="3.30") as mdf3:
                mdf3.start_time = datetime.now()
                mdf3.save(mdf3_path, overwrite=True)
            mdf3_path.rename(file_path)

            handle = self.service.Open(exd_api.Identifier(url=file_path.as_uri(), parameters=""), self.mock_context)
            try:
                self.assertIsNotNone(handle.uuid)
            finally:
                self.service.Close(handle, self.mock_context)

    def test_open_mdf4_file_with_dat_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.dat"
            mdf4_path = Path(temp_dir) / "test.mf4"
            with MDF(version="4.10") as mdf4:
                mdf4.save(mdf4_path, overwrite=True)
            mdf4_path.rename(file_path)

            handle = self.service.Open(exd_api.Identifier(url=file_path.as_uri(), parameters=""), self.mock_context)
            try:
                self.assertIsNotNone(handle.uuid)
            finally:
                self.service.Close(handle, self.mock_context)

    def test_reject_non_mdf_file_with_dat_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.dat"
            file_path.write_bytes(b"not an MDF file")

            with self.assertRaises(grpc.RpcError):
                self.service.Open(exd_api.Identifier(url=file_path.as_uri(), parameters=""), self.mock_context)

            self.assertEqual(self.mock_context.code(), grpc.StatusCode.FAILED_PRECONDITION)
            self.assertEqual(self.mock_context.details(), "Not my file!")

    def test_dat_factory_raises_not_my_file_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.dat"
            file_path.write_bytes(b"not an MDF file")

            with self.assertRaises(NotMyFileError):
                ExternalDataFile.create(str(file_path), "")

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

    def test_fill_structure_without_acq_name(self):
        real_mdf = MDF("data/simple.mf4")
        try:
            real_group = real_mdf.groups[0]
            fake_group = SimpleNamespace(
                channel_group=SimpleNamespace(comment=None, cycles_nr=real_group.channel_group.cycles_nr),
                channels=real_group.channels,
            )
            fake_mdf = SimpleNamespace(
                groups=[fake_group],
                start_time=real_mdf.start_time,
                header=SimpleNamespace(description=None, _common_properties=None),
            )

            instance = ExternalDataFile.__new__(ExternalDataFile)
            instance._log = __import__("logging").getLogger(__name__)
            instance.file_path = "test.mf4"
            instance.mdf4 = fake_mdf
            instance.values_raw = False
            instance.values_ignore_value2text_conversions = False

            structure = exd_api.StructureResult()
            instance.fill_structure(structure)

            self.assertEqual(structure.groups[0].name, "Group 0")
            self.assertEqual(structure.groups[0].attributes.variables["description"].string_array.values[0], "")
        finally:
            real_mdf.close()

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
