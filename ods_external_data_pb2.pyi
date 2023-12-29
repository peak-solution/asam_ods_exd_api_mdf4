import ods_pb2 as _ods_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Empty(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class Handle(_message.Message):
    __slots__ = ["uuid"]
    UUID_FIELD_NUMBER: _ClassVar[int]
    uuid: str
    def __init__(self, uuid: _Optional[str] = ...) -> None: ...

class Identifier(_message.Message):
    __slots__ = ["parameters", "url"]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    parameters: str
    url: str
    def __init__(self, url: _Optional[str] = ..., parameters: _Optional[str] = ...) -> None: ...

class StructureRequest(_message.Message):
    __slots__ = ["channel_names", "handle", "suppress_attributes", "suppress_channels"]
    CHANNEL_NAMES_FIELD_NUMBER: _ClassVar[int]
    HANDLE_FIELD_NUMBER: _ClassVar[int]
    SUPPRESS_ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    SUPPRESS_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    channel_names: _containers.RepeatedScalarFieldContainer[str]
    handle: Handle
    suppress_attributes: bool
    suppress_channels: bool
    def __init__(self, handle: _Optional[_Union[Handle, _Mapping]] = ..., suppress_channels: bool = ..., suppress_attributes: bool = ..., channel_names: _Optional[_Iterable[str]] = ...) -> None: ...

class StructureResult(_message.Message):
    __slots__ = ["attributes", "groups", "identifier", "name"]
    class Channel(_message.Message):
        __slots__ = ["attributes", "data_type", "id", "name", "unit_string"]
        ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
        DATA_TYPE_FIELD_NUMBER: _ClassVar[int]
        ID_FIELD_NUMBER: _ClassVar[int]
        NAME_FIELD_NUMBER: _ClassVar[int]
        UNIT_STRING_FIELD_NUMBER: _ClassVar[int]
        attributes: _ods_pb2.ContextVariables
        data_type: _ods_pb2.DataTypeEnum
        id: int
        name: str
        unit_string: str
        def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., data_type: _Optional[_Union[_ods_pb2.DataTypeEnum, str]] = ..., unit_string: _Optional[str] = ..., attributes: _Optional[_Union[_ods_pb2.ContextVariables, _Mapping]] = ...) -> None: ...
    class Group(_message.Message):
        __slots__ = ["attributes", "channels", "id", "name", "number_of_rows", "total_number_of_channels"]
        ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
        CHANNELS_FIELD_NUMBER: _ClassVar[int]
        ID_FIELD_NUMBER: _ClassVar[int]
        NAME_FIELD_NUMBER: _ClassVar[int]
        NUMBER_OF_ROWS_FIELD_NUMBER: _ClassVar[int]
        TOTAL_NUMBER_OF_CHANNELS_FIELD_NUMBER: _ClassVar[int]
        attributes: _ods_pb2.ContextVariables
        channels: _containers.RepeatedCompositeFieldContainer[StructureResult.Channel]
        id: int
        name: str
        number_of_rows: int
        total_number_of_channels: int
        def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., total_number_of_channels: _Optional[int] = ..., number_of_rows: _Optional[int] = ..., channels: _Optional[_Iterable[_Union[StructureResult.Channel, _Mapping]]] = ..., attributes: _Optional[_Union[_ods_pb2.ContextVariables, _Mapping]] = ...) -> None: ...
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    GROUPS_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    attributes: _ods_pb2.ContextVariables
    groups: _containers.RepeatedCompositeFieldContainer[StructureResult.Group]
    identifier: Identifier
    name: str
    def __init__(self, identifier: _Optional[_Union[Identifier, _Mapping]] = ..., name: _Optional[str] = ..., groups: _Optional[_Iterable[_Union[StructureResult.Group, _Mapping]]] = ..., attributes: _Optional[_Union[_ods_pb2.ContextVariables, _Mapping]] = ...) -> None: ...

class ValuesExRequest(_message.Message):
    __slots__ = ["attributes", "channel_names", "group_id", "handle", "limit", "start"]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_NAMES_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    HANDLE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    attributes: _containers.RepeatedScalarFieldContainer[str]
    channel_names: _containers.RepeatedScalarFieldContainer[str]
    group_id: int
    handle: Handle
    limit: int
    start: int
    def __init__(self, handle: _Optional[_Union[Handle, _Mapping]] = ..., group_id: _Optional[int] = ..., channel_names: _Optional[_Iterable[str]] = ..., attributes: _Optional[_Iterable[str]] = ..., start: _Optional[int] = ..., limit: _Optional[int] = ...) -> None: ...

class ValuesExResult(_message.Message):
    __slots__ = ["unit_map", "values"]
    class UnitMapEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: str
        def __init__(self, key: _Optional[int] = ..., value: _Optional[str] = ...) -> None: ...
    UNIT_MAP_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    unit_map: _containers.ScalarMap[int, str]
    values: _ods_pb2.DataMatrix
    def __init__(self, values: _Optional[_Union[_ods_pb2.DataMatrix, _Mapping]] = ..., unit_map: _Optional[_Mapping[int, str]] = ...) -> None: ...

class ValuesRequest(_message.Message):
    __slots__ = ["channel_ids", "group_id", "handle", "limit", "start"]
    CHANNEL_IDS_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    HANDLE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    channel_ids: _containers.RepeatedScalarFieldContainer[int]
    group_id: int
    handle: Handle
    limit: int
    start: int
    def __init__(self, handle: _Optional[_Union[Handle, _Mapping]] = ..., group_id: _Optional[int] = ..., channel_ids: _Optional[_Iterable[int]] = ..., start: _Optional[int] = ..., limit: _Optional[int] = ...) -> None: ...

class ValuesResult(_message.Message):
    __slots__ = ["channels", "id"]
    class ChannelValues(_message.Message):
        __slots__ = ["flags", "id", "values"]
        FLAGS_FIELD_NUMBER: _ClassVar[int]
        ID_FIELD_NUMBER: _ClassVar[int]
        VALUES_FIELD_NUMBER: _ClassVar[int]
        flags: _ods_pb2.LongArray
        id: int
        values: _ods_pb2.DataMatrix.Column.UnknownArray
        def __init__(self, id: _Optional[int] = ..., values: _Optional[_Union[_ods_pb2.DataMatrix.Column.UnknownArray, _Mapping]] = ..., flags: _Optional[_Union[_ods_pb2.LongArray, _Mapping]] = ...) -> None: ...
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedCompositeFieldContainer[ValuesResult.ChannelValues]
    id: int
    def __init__(self, id: _Optional[int] = ..., channels: _Optional[_Iterable[_Union[ValuesResult.ChannelValues, _Mapping]]] = ...) -> None: ...
