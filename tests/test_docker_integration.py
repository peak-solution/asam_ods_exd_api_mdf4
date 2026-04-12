import logging
import pathlib
import socket
import subprocess
import time
import unittest

import grpc
from google.protobuf.json_format import MessageToJson
from ods_exd_api_box import exd_api, exd_grpc, ods


class TestDockerContainer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Docker-Image bauen
        subprocess.run(["docker", "build", "-t", "asam-ods-exd-api-mdf4", "."], check=True)

        # Remove any stale container with the same name
        subprocess.run(["docker", "rm", "-f", "test_container"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        example_file_path = pathlib.Path.joinpath(pathlib.Path(__file__).parent.resolve(), "..", "data")
        data_folder = pathlib.Path(example_file_path).absolute().resolve()
        cp = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                "test_container",
                "-p",
                "50051:50051",
                "-v",
                f"{data_folder}:/data",
                "asam-ods-exd-api-mdf4",
            ],
            stdout=subprocess.PIPE,
            check=True,
        )
        cls.container_id = cp.stdout.decode().strip()
        cls.__wait_for_port_ready()

    @classmethod
    def tearDownClass(cls):
        # Container stoppen
        subprocess.run(["docker", "stop", "test_container"], check=True)

    @classmethod
    def __wait_for_port_ready(cls, host="localhost", port=50051, timeout=30):
        start_time = time.time()
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return
            if time.time() - start_time > timeout:
                raise TimeoutError("Port did not become ready in time.")
            time.sleep(0.5)

    def test_container_health(self):
        channel = grpc.insecure_channel("localhost:50051")
        stub = exd_grpc.ExternalDataReaderStub(channel)
        self.assertIsNotNone(stub)
        grpc.channel_ready_future(channel).result(timeout=5)

    def test_structure(self):
        with grpc.insecure_channel("localhost:50051") as channel:
            service = exd_grpc.ExternalDataReaderStub(channel)

            handle = service.Open(exd_api.Identifier(url="/data/simple.mf4", parameters=""), None)
            try:
                structure = service.GetStructure(exd_api.StructureRequest(handle=handle), None)
                logging.info(MessageToJson(structure))

                self.assertEqual(structure.name, "simple.mf4")
                self.assertEqual(len(structure.groups), 1)
                self.assertEqual(structure.groups[0].number_of_rows, 563)
                self.assertEqual(len(structure.groups[0].channels), 10)
                self.assertEqual(structure.groups[0].id, 0)
                logging.info(MessageToJson(structure))
                self.assertEqual(structure.groups[0].channels[0].id, 0)
            finally:
                service.Close(handle, None)

    def test_get_values(self):
        with grpc.insecure_channel("localhost:50051") as channel:
            service = exd_grpc.ExternalDataReaderStub(channel)

            handle = service.Open(exd_api.Identifier(url="/data/simple.mf4", parameters=""), None)

            try:
                values = service.GetValues(
                    exd_api.ValuesRequest(handle=handle, group_id=0, channel_ids=[0, 1, 2, 3], start=0, limit=4),
                    None,  #
                )
                self.assertEqual(values.id, 0)
                self.assertEqual(len(values.channels), 4)
                self.assertEqual(values.channels[0].id, 0)
                self.assertEqual(values.channels[1].id, 1)
                logging.info(MessageToJson(values))

                self.assertEqual(values.channels[0].values.data_type, ods.DataTypeEnum.DT_DOUBLE)
                self.assertSequenceEqual(
                    values.channels[0].values.double_array.values, [0.0, 17905500.0, 30515300.0, 48317800.0]
                )
                self.assertEqual(values.channels[1].values.data_type, ods.DataTypeEnum.DT_LONGLONG)
                self.assertSequenceEqual(
                    values.channels[1].values.longlong_array.values,
                    [1686082945335777300, 1686082945353682800, 1686082945366292600, 1686082945384095100],
                )
            finally:
                service.Close(handle, None)
