"""EXD API implementation for MDF 4 files"""
import os
from pathlib import Path
import threading
from urllib.parse import urlparse, unquote
from urllib.request import url2pathname

import grpc
import ods_pb2 as ods
import ods_external_data_pb2 as exd_api
import ods_external_data_pb2_grpc

from asammdf import MDF


class ExternalDataReader(ods_external_data_pb2_grpc.ExternalDataReader):

    def Open(self, request, context):
        file_path = Path(self.__get_path(request.url))
        if not file_path.is_file():
            raise Exception(f'file "{request.url}" not accessible')

        connection_id = self.__open_mdf(request)

        rv = exd_api.Handle(uuid=connection_id)
        return rv

    def Close(self, request, context):
        self.__close_mdf(request)
        return exd_api.Empty()

    def GetStructure(self, request, context):

        if request.suppress_channels or request.suppress_attributes or 0 != len(request.channel_names):
            context.set_code(grpc.StatusCode.UNIMPLEMENTED)
            context.set_details('Method not implemented!')
            raise NotImplementedError('Method not implemented!')

        identifier = self.connection_map[request.handle.uuid]
        mdf4 = self.__get_mdf(request.handle)

        rv = exd_api.StructureResult(identifier=identifier)
        rv.name = Path(identifier.url).name
        rv.attributes.variables["start_time"].string_array.values.append(mdf4.start_time.strftime("%Y%m%d%H%M%S%f"))

        group_index = 0
        for group in mdf4.groups:

            new_group = exd_api.StructureResult.Group()
            new_group.name = group.channel_group.acq_name
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
                new_channel.data_type = self.__get_channel_data_type(channel)
                new_channel.unit_string = channel.unit
                new_group.channels.append(new_channel)
                i += 1

            rv.groups.append(new_group)
            group_index += 1

        return rv

    def GetValues(self, request, context):

        mdf4 = self.__get_mdf(request.handle)

        if request.group_id < 0 or request.group_id >= len(mdf4.groups):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f'Invalid group id {request.group_id}!')
            raise NotImplementedError(f'Invalid group id {request.group_id}!')

        group = mdf4.groups[request.group_id]

        nr_of_rows = group.channel_group.cycles_nr
        if request.start >= nr_of_rows:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f'Channel start index {request.start} out of range!')
            raise NotImplementedError(f'Channel start index {request.start} out of range!')

        end_index = request.start + request.limit
        if end_index >= nr_of_rows:
            end_index = nr_of_rows

        channels_to_load = []
        for channel_id in request.channel_ids:
            if channel_id >= len(group.channels):
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f'Invalid channel id {channel_id}!')
                raise NotImplementedError(f'Invalid channel id {channel_id}!')
            channels_to_load.append((None, request.group_id, channel_id))

        data = mdf4.select(channels_to_load, 
                           raw=False,
                           ignore_value2text_conversions=False,
                           record_offset=request.start, 
                           record_count=request.limit,
                           copy_master=False)
        if len(data) != len(request.channel_ids):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f'Number read {len(data)} does not match requested channel count {len(request.channel_ids)} in {mdf4.name.name}!')
            raise NotImplementedError(f'Number read {len(data)} does not match requested channel count {len(request.channel_ids)} in {mdf4.name.name}!')

        rv = exd_api.ValuesResult(id=request.group_id)
        for index, signal in enumerate(data, start=0):
            section = signal.samples
            channel_id = request.channel_ids[index]
            channel = group.channels[channel_id]
            channel_datatype = self.__get_channel_data_type(channel)

            new_channel_values = exd_api.ValuesResult.ChannelValues()
            new_channel_values.id = channel_id
            new_channel_values.values.data_type = channel_datatype

            if channel_datatype == ods.DataTypeEnum.DT_BOOLEAN:
                new_channel_values.values.boolean_array.values.extend(section)
            elif channel_datatype == ods.DataTypeEnum.DT_BYTE:
                new_channel_values.values.byte_array.values = section.tobytes()
            elif channel_datatype == ods.DataTypeEnum.DT_SHORT:
                new_channel_values.values.long_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_LONG:
                new_channel_values.values.long_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_LONGLONG:
                new_channel_values.values.longlong_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_FLOAT:
                new_channel_values.values.float_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_DOUBLE:
                new_channel_values.values.double_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_STRING:
                new_channel_values.values.string_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_BYTESTR:
                for item in section:
                    new_channel_values.values.bytestr_array.values.append(item.tobytes())
            else:
                raise NotImplementedError(f'Unknown np datatype {section.dtype} for type {channel_datatype} in {mdf4.name.name}!')

            rv.channels.append(new_channel_values)

        return rv

    def GetValuesEx(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def __get_channel_data_type(self, channel):
        rv = self.__get_channel_data_type_base(channel)
        if channel.conversion is not None:
            if ods.DataTypeEnum.DT_STRING == rv:
                if 9 == channel.conversion.conversion_type:
                    # text to value tabular look-up
                    return ods.DataTypeEnum.DT_DOUBLE
            elif channel.conversion.conversion_type in [1, 2, 3, 4, 5]:
                return ods.DataTypeEnum.DT_DOUBLE
            elif channel.conversion.conversion_type in [7, 8]:
                return ods.DataTypeEnum.DT_STRING
        return rv

    def __get_channel_data_type_base(self, channel):
        # [width="100",options="header"]
        # |====================
        # | number | cn_bit_count | DataTypeEnum | description
        # | _Integer data types:_ | | |
        # | 0, 1   | 1           | DT_BOOLEAN  | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 2 - 8       | DT_BYTE     | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 8 - 15      | DT_SHORT    | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 16 - 31     | DT_LONG     | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 32 - 63     | DT_LONGLONG | unsigned integer (LE Byte order, BE Byte order)
        # | 2, 3   | 64 - 64     | DT_DOUBLE   | signed integer (two’s complement) (LE Byte order, BE Byte order)
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
            if 32 <= mdf4_data_bit_count <= 63:
                return ods.DataTypeEnum.DT_LONGLONG
            if 64 <= mdf4_data_bit_count <= 64:
                return ods.DataTypeEnum.DT_DOUBLE
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

    def __init__(self):
        self.connect_count = 0
        self.connection_map = {}
        self.file_map = {}
        self.lock = threading.Lock()

    def __get_id(self, identifier):
        self.connect_count = self.connect_count + 1
        rv = str(self.connect_count)
        self.connection_map[rv] = identifier
        return rv

    def __uri_to_path(self, uri):
        parsed = urlparse(uri)
        host = "{0}{0}{mnt}{0}".format(os.path.sep, mnt=parsed.netloc)
        return os.path.normpath(
            os.path.join(host, url2pathname(unquote(parsed.path)))
        )

    def __get_path(self, file_url):
        final_path = self.__uri_to_path(file_url)
        return final_path
    
    def __open_mdf(self, identifier):
        with self.lock:
            identifier.parameters
            connection_id = self.__get_id(identifier)
            connection_url = self.__get_path(identifier.url)
            if connection_url not in self.file_map:
                self.file_map[connection_url] = {"mdf4": MDF(connection_url), "ref_count": 0}
            self.file_map[connection_url]["ref_count"] = self.file_map[connection_url]["ref_count"] + 1
            return connection_id

    def __get_mdf(self, handle):
        identifier = self.connection_map[handle.uuid]
        connection_url = self.__get_path(identifier.url)
        return self.file_map[connection_url]["mdf4"]

    def __close_mdf(self, handle):
        with self.lock:
            identifier = self.connection_map[handle.uuid]
            connection_url = self.__get_path(identifier.url)
            if self.file_map[connection_url]["ref_count"] > 1:
                self.file_map[connection_url]["ref_count"] = self.file_map[connection_url]["ref_count"] - 1
            else:
                self.file_map[connection_url]["mdf4"].close()
                del self.file_map[connection_url]


if __name__ == '__main__':

    from google.protobuf.json_format import MessageToJson

    external_data_reader = ExternalDataReader()

    handle = external_data_reader.Open(exd_api.Identifier(url="file://C:/build/asammdf/data/pendulum_1686037830.mf4"), None)
    request = exd_api.StructureRequest(handle=handle)
    structure = external_data_reader.GetStructure(request, None)
    print(MessageToJson(structure))

    print(MessageToJson(external_data_reader.GetValues(
        exd_api.ValuesRequest(handle=handle, group_id=0, channel_ids=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], start=0, limit=10), None)))
