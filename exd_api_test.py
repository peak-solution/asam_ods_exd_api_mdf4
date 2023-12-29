# Prepare python to use GRPC interface:
# python -m grpc_tools.protoc --proto_path=proto_src --pyi_out=. --python_out=. --grpc_python_out=. ods.proto ods_external_data.proto

import unittest
import pathlib
import ods_external_data_pb2 as oed

from external_data_reader import ExternalDataReader
from google.protobuf.json_format import MessageToJson

class TestStringMethods(unittest.TestCase):

    def _get_example_file_path(self, file_name):
        example_file_path = pathlib.Path.joinpath(pathlib.Path(__file__).parent.resolve(), 'data', file_name)
        return pathlib.Path(example_file_path).as_uri().replace('///', '//')

    def test_open(self):
        service = ExternalDataReader()
        handle = service.Open(oed.Identifier(url=self._get_example_file_path('simple.mf4')), None)
        try:
            pass
        finally:
            service.Close(handle, None)

    def test_structure(self):
        service = ExternalDataReader()
        handle = service.Open(oed.Identifier(url=self._get_example_file_path('simple.mf4')), None)
        try:
            structure = service.GetStructure(oed.StructureRequest(handle=handle), None)
            self.assertEqual(structure.name, 'simple.mf4')
            self.assertEqual(len(structure.groups), 1)
            self.assertEqual(structure.groups[0].number_of_rows, 563)
            self.assertEqual(len(structure.groups[0].channels), 10)
            self.assertEqual(structure.groups[0].id, 0)
            #print(MessageToJson(structure))
            self.assertEqual(structure.groups[0].channels[0].id, 0)
        finally:
            service.Close(handle, None)

    def test_get_values(self):
        service = ExternalDataReader()
        handle = service.Open(oed.Identifier(url=self._get_example_file_path('simple.mf4')), None)
        try:
            values = service.GetValues(oed.ValuesRequest(handle=handle,
                                                         group_id=0,#
                                                         channel_ids=[0,1,2,3],
                                                         start=0,
                                                         limit=10), None)
            self.assertEqual(values.id, 0)
            self.assertEqual(len(values.channels), 4)
            self.assertEqual(values.channels[0].id, 0)
            self.assertEqual(values.channels[1].id, 1)
            #print(MessageToJson(values))
        finally:
            service.Close(handle, None)



if __name__ == '__main__':
    unittest.main()