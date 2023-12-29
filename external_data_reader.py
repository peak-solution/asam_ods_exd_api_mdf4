"""EXD API implementation for MDF 4 files"""
import os
import numpy as np
import pandas as pd
from pathlib import Path
from urllib.parse import unquote, urlparse

import ods_pb2 as ods
import ods_external_data_pb2 as exd_api
import ods_external_data_pb2_grpc

from asammdf import MDF

class ExternalDataReader(ods_external_data_pb2_grpc.ExternalDataReader):

    def __init__(self):
        self.connect_count = 0
        self.connection_map = {}

    def _get_id(self, identifier):
        self.connect_count = self.connect_count + 1
        rv = str(self.connect_count)
        self.connection_map[rv] = identifier
        return rv

    def _get_path(self, file_url):
        p = urlparse(file_url)
        final_path = os.path.abspath(os.path.join(p.netloc, p.path))
        return final_path

    def Open(self, request, context):
        file_path = Path(self._get_path(request.url))
        if not file_path.is_file():
            raise Exception(f'file "{request.url}" not accessible')
        
        request.parameters
        connection_id = self._get_id(request)

        rv = exd_api.Handle(uuid=connection_id)
        return rv

    def GetStructure(self, request, context):

        if request.suppress_channels or request.suppress_attributes or 0 != len(request.channel_names):
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            context.set_details('Method not implemented!')
            raise NotImplementedError('Method not implemented!')

        identifier = self.connection_map[request.handle.uuid]

        with MDF(self._get_path(identifier.url)) as mdf4:

            rv = exd_api.StructureResult(identifier=identifier)
            rv.name = Path(identifier.url).name
            rv.attributes.variables["start_time"].string_array.values.append(mdf4.start_time.strftime("%Y%m%d%H%M%S%f"))

            group_index = 0
            for group in mdf4.groups :

                new_group = exd_api.StructureResult.Group()
                new_group.name = group.channel_group.comment
                new_group.id = group_index
                new_group.total_number_of_channels = len(group.channels)
                new_group.number_of_rows = group.channel_group.cycles_nr
                new_group.attributes.variables["description"].string_array.values.append(group.channel_group.comment)

                i = 0
                for channel in group.channels:
                    new_channel = exd_api.StructureResult.Channel()
                    new_channel.name = channel.name
                    new_channel.id = i
                    new_channel.attributes.variables["description"].string_array.values.append(channel.comment)
                    new_channel.data_type = self._get_channel_data_type(channel)
                    new_channel.unit_string = channel.unit
                    new_group.channels.append(new_channel)
                    i += 1

                rv.groups.append(new_group)
                group_index += 1

            return rv

    def GetValues(self, request, context):
        identifier = self.connection_map[request.handle.uuid]
        request.channel_ids
        request.start
        request.limit

        with MDF(self._get_path(identifier.url)) as mdf4:

            if request.group_id < 0 or request.group_id >= len(mdf4.groups):
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f'Invalid group id {request.group_id}!')
                raise NotImplementedError(f'Invalid group id {request.group_id}!')

            data = mdf4.get_group(request.group_id)

            if request.start >= data.shape[0]:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f'Channel start index {request.start} out of range!')
                raise NotImplementedError(f'Channel start index {request.start} out of range!')

            end_index = request.start + request.limit
            if end_index >= data.shape[0]:
                end_index = data.shape[0]

            rv = exd_api.ValuesResult(id=request.group_id)
            for channel_id in request.channel_ids:
                if channel_id > data.shape[1]:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details(f'Invalid channel id {channel_id}!')
                    raise NotImplementedError(f'Invalid channel id {channel_id}!')
                
                section = data.iloc[request.start:end_index, channel_id].index if 0 == channel_id else data.iloc[request.start:end_index, channel_id - 1]

                new_channel_values = exd_api.ValuesResult.ChannelValues()
                new_channel_values.id = channel_id
                if np.float64 == section.dtype:
                    new_channel_values.values.data_type = ods.DataTypeEnum.DT_DOUBLE
                    new_channel_values.values.double_array.values[:] = section.values
                if np.float32 == section.dtype:
                    new_channel_values.values.data_type = ods.DataTypeEnum.DT_FLOAT
                    new_channel_values.values.float_array.values[:] = section.values
                elif np.int64 == section.dtype:
                    new_channel_values.values.data_type = ods.DataTypeEnum.DT_LONGLONG
                    new_channel_values.values.longlong_array.values[:] = section.values
                elif np.int32 == section.dtype:
                    new_channel_values.values.data_type = ods.DataTypeEnum.DT_LONG
                    new_channel_values.values.long_array.values[:] = section.values

                rv.channels.append(new_channel_values)

            return rv

    def GetValuesEx(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Close(self, request, context):
        identifier = self.connection_map[request.uuid]
        return exd_api.Empty()

    def _get_channel_data_type(self, channel):
        # [width="100",options="header"]
        # |====================
        # | number | cn_bit_count | DataTypeEnum | description
        # | _Integer data types:_ | | |
        # | 0, 1   | 1           | DT_BOOLEAN  | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 2 - 8       | DT_BYTE     | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 8 - 15      | DT_SHORT    | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 16 - 31     | DT_LONG     | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 32 - 64     | DT_LONGLONG | unsigned integer (LE Byte order, BE Byte order)
        # | 2, 3   | 1           | DT_BOOLEAN  | signed integer (two’s complement) (LE Byte order, BE Byte order)
        # | 2, 3   | 2 - 16      | DT_SHORT    | signed integer (two’s complement) (LE Byte order, BE Byte order)
        # | 2, 3   | 17 - 32     | DT_LONG     | signed integer (two’s complement) (LE Byte order, BE Byte order)
        # | 2, 3   | 33 - 64     | DT_LONGLONG | signed integer (two’s complement) (LE Byte order, BE Byte order)
        # | _Floating-point data types:_ | | |
        # | 4, 5   | 16, 32      | DT_FLOAT    | IEEE 754 floating-point format (LE Byte order, BE Byte order)
        # | 4, 5   | 64          | DT_DOUBLE   | IEEE 754 floating-point format (LE Byte order, BE Byte order)
        # | _String data types:_ | | |
        # | 6      |             | DT_STRING   | string (SBC, standard ISO-8859-1 encoded (Latin), NULL terminated)
        # | 7      |             | DT_STRING   | string (UTF-8 encoded, NULL terminated)
        # | 8      |             | DT_STRING   | string (UTF-16 encoded LE Byte order, NULL terminated)
        # | 9      |             | DT_STRING   | string (UTF-16 encoded BE Byte order, NULL terminated)
        # | _Complex data types:_ | | |
        # | 10     |             | DT_BYTESTR  | byte array with unknown content (e.g. structure)
        # | 11     |             | DT_BYTESTR  | MIME sample (sample is Byte Array with MIME content-type specified in cn_md_unit)
        # | 12     |             | DT_BYTESTR  | MIME stream (all samples of channel represent a stream with MIME content-type specified in cn_md_unit)
        # | 13     |             | DT_DATE     | CANopen date (Based on 7 Byte CANopen Date data structure, see Table 39)
        # | 14     |             | DT_DATE     | CANopen time (Based on 6 Byte CANopen Time data structure, see Table 40)
        # | 15, 16 | 16, 32      | DT_COMPLEX  | complex number (real part followed by imaginary part, stored as two floating-point data, both with 2, 4 or 8 Byte, LE Byte order, BE Byte order)
        # | 15, 16 | 64          | DT_DCOMPLEX | complex number (real part followed by imaginary part, stored as two floating-point data, both with 2, 4 or 8 Byte, LE Byte order, BE Byte order)
        # |====================
        mdf4_data_type = channel.data_type
        mdf4_data_bit_count = channel.bit_count
        if 0 <= mdf4_data_type <= 1:
            if 1 == mdf4_data_bit_count:
                return ods.DataTypeEnum.DT_BOOLEAN
            if 2 <= mdf4_data_bit_count <= 8:
                return ods.DataTypeEnum.DT_BYTE
            if 8 <= mdf4_data_bit_count <= 15:
                return ods.DataTypeEnum.DT_SHORT
            if 16 <= mdf4_data_bit_count <= 31:
                return ods.DataTypeEnum.DT_LONG
            if 32 <= mdf4_data_bit_count <= 64:
                return ods.DataTypeEnum.DT_LONGLONG
        if 2 <= mdf4_data_type <= 3:
            if 1 == mdf4_data_bit_count:
                return ods.DataTypeEnum.DT_BOOLEAN
            if 2 <= mdf4_data_bit_count <= 16:
                return ods.DataTypeEnum.DT_SHORT
            if 17 <= mdf4_data_bit_count <= 32:
                return ods.DataTypeEnum.DT_LONG
            if 33 <= mdf4_data_bit_count <= 64:
                return ods.DataTypeEnum.DT_LONGLONG
        if 4 <= mdf4_data_type <= 5:
            if 1 <= mdf4_data_bit_count <= 32:
                return ods.DataTypeEnum.DT_FLOAT
            if 33 <= mdf4_data_bit_count <= 64:
                return ods.DataTypeEnum.DT_DOUBLE
        if 6 <= mdf4_data_type <= 9:
            return ods.DataTypeEnum.DT_STRING
        if 10 <= mdf4_data_type <= 12:
            return ods.DataTypeEnum.DT_BYTESTR
        if 13 <= mdf4_data_type <= 14:
            return ods.DataTypeEnum.DT_DATE
        if 15 <= mdf4_data_type <= 16:
            if 1 <= mdf4_data_bit_count <= 32:
                return ods.DataTypeEnum.DT_COMPLEX
            if 33 <= mdf4_data_bit_count <= 64:
                return ods.DataTypeEnum.DT_DCOMPLEX

        return ods.DataTypeEnum.DT_DOUBLE


if __name__ == '__main__':

    from google.protobuf.json_format import MessageToJson

    external_data_reader = ExternalDataReader()

    handle = external_data_reader.Open(exd_api.Identifier(url="file://C:/build/asammdf/data/pendulum_1686037830.mf4"), None)
    request = exd_api.StructureRequest(handle=handle)
    structure = external_data_reader.GetStructure(request, None)
    print(MessageToJson(structure))

    print(MessageToJson(external_data_reader.GetValues(
        exd_api.ValuesRequest(handle=handle, group_id=0, channel_ids=[0,1,2,3,4,5,6,7,8,9], start=0, limit=10), None)))