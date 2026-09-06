"""ASAM ODS EXD API implementation for MDF4 files."""

from __future__ import annotations

import logging
from typing import Any, cast, override

import numpy as np
from asammdf import MDF
from asammdf.blocks.v4_blocks import Channel, ChannelConversion, HeaderBlock
from ods_exd_api_box import ExdFileInterface, exd_api, ods
from ods_exd_api_box.utils import ParamParser


class ExternalDataFile(ExdFileInterface):
    """Class for handling MDF4 files."""

    # Pre-built decoders for string encodings to avoid recreation on every call
    _latin1_decoder = np.frompyfunc(lambda b: b.decode("latin-1"), 1, 1)
    _utf8_decoder = np.frompyfunc(lambda b: b.decode("utf-8"), 1, 1)
    _utf16le_decoder = np.frompyfunc(lambda b: (b if len(b) % 2 == 0 else b + b"\x00").decode("utf-16-le"), 1, 1)
    _utf16be_decoder = np.frompyfunc(lambda b: (b if len(b) % 2 == 0 else b + b"\x00").decode("utf-16-be"), 1, 1)

    @classmethod
    @override
    def create(cls, file_path: str, parameters: str) -> ExdFileInterface:
        """Factory method to create a file handler instance."""
        return cls(file_path, parameters)

    def _get_bool(self, params: dict[str, Any], name: str, default: bool = False) -> bool:
        val = params.get(name, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes")
        if isinstance(val, (int, float)):
            return val != 0
        return default

    @override
    def __init__(self, file_path: str, parameters: str = ""):
        self._log = logging.getLogger(__name__)

        self._log.debug("Initializing ExternalDataFile with path: %s and parameters: %s", file_path, parameters)
        self.file_path = file_path
        self.parameters = parameters
        params = ParamParser.parse_params(parameters)
        self.values_raw: bool = self._get_bool(params, "values_raw", False)
        self.values_ignore_value2text_conversions: bool = self._get_bool(
            params, "values_ignore_value2text_conversions", False
        )
        self.mdf4 = MDF(file_path)
        self._log.debug("ExternalDataFile initialized")

    @override
    def close(self) -> None:
        """Close the external data file."""
        self.mdf4.close()
        self._log.debug("ExternalDataFile closed")

    @override
    def fill_structure(self, structure: exd_api.StructureResult) -> None:
        """Fill the structure of the external data file."""
        mdf4 = self.mdf4
        self._log.debug("Building structure for file: %s", self.file_path)

        start_time_ods = mdf4.start_time.strftime("%Y%m%d%H%M%S%f")

        structure.attributes.variables["start_time"].string_array.values.append(start_time_ods)
        self.__add_file_header(mdf4.header, structure.attributes)  # type: ignore

        self._log.debug("Found %d groups in MDF", len(mdf4.groups))
        for group_index, group in enumerate(mdf4.groups):
            group_any = cast(Any, group)
            new_group = exd_api.StructureResult.Group()
            new_group.name = (
                group_any.channel_group.acq_name
                if group_any.channel_group.acq_name is not None
                else f"Group {group_index}"
            )  # type: ignore
            new_group.id = group_index
            new_group.total_number_of_channels = len(group_any.channels)
            new_group.number_of_rows = group_any.channel_group.cycles_nr
            new_group.attributes.variables["description"].string_array.values.append(group_any.channel_group.comment)
            new_group.attributes.variables["measurement_begin"].string_array.values.append(start_time_ods)

            independent_added = False
            for channel_index, channel in enumerate(group_any.channels):
                new_channel = exd_api.StructureResult.Channel()
                new_channel.name = channel.name
                new_channel.id = channel_index
                new_channel.data_type = self.__get_channel_data_type(channel)  # type: ignore
                new_channel.unit_string = channel.unit
                if channel.comment is not None and "" != channel.comment:  # type: ignore
                    new_channel.attributes.variables["description"].string_array.values.append(channel.comment)
                if channel.channel_type in (2, 3):  # MASTER or VIRTUAL_MASTE channel
                    if not independent_added:
                        new_channel.attributes.variables["independent"].long_array.values.append(1)
                        independent_added = True
                    else:
                        self._log.warning(
                            "Group %s has more than one master channel. Only the first will be marked as independent. "
                            "'%s' (type=%s) is ignored.",
                            new_group.name,
                            new_channel.name,
                            channel.channel_type,
                        )
                new_group.channels.append(new_channel)

            structure.groups.append(new_group)
            self._log.debug(
                "Added group id=%d name=%s channels=%d rows=%d",
                new_group.id,
                new_group.name,
                len(new_group.channels),
                new_group.number_of_rows,
            )

    @override
    def get_values(self, request: exd_api.ValuesRequest) -> exd_api.ValuesResult:
        """Get values from the external data file."""
        mdf4 = self.mdf4
        self._log.debug(
            "GetValues request group_id=%d start=%d limit=%d channel_count=%d",
            request.group_id,
            request.start,
            request.limit,
            len(request.channel_ids),
        )

        if request.group_id < 0 or request.group_id >= len(mdf4.groups):
            raise ValueError(f"Invalid group id {request.group_id}!")

        group = mdf4.groups[request.group_id]

        nr_of_rows = group.channel_group.cycles_nr
        if request.start > nr_of_rows:
            raise ValueError(f"Channel start index {request.start} out of range!")

        end_index = request.start + request.limit
        if end_index >= nr_of_rows:
            end_index = nr_of_rows
        self._log.debug("Reading rows in range [%d, %d) out of %d", request.start, end_index, nr_of_rows)

        channels_to_load = []
        for channel_id in request.channel_ids:
            if channel_id >= len(group.channels):
                raise ValueError(f"Invalid channel id {channel_id}!")
            channels_to_load.append((None, request.group_id, channel_id))

        data = mdf4.select(
            channels_to_load,
            raw=self.values_raw,
            ignore_value2text_conversions=self.values_ignore_value2text_conversions,
            record_offset=request.start,
            record_count=request.limit,
            copy_master=False,
        )
        if len(data) != len(request.channel_ids):
            raise ValueError(
                f"Number read {len(data)} does not match requested channel count "
                f"{len(request.channel_ids)} in {mdf4.name.name}!"
            )

        rv = exd_api.ValuesResult(id=request.group_id)
        for signal_index, signal in enumerate(data, start=0):
            section = signal.samples
            channel_id = request.channel_ids[signal_index]
            channel = group.channels[channel_id]
            channel_datatype = self.__get_channel_data_type(channel)  # type: ignore

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
                section_array = np.asarray(section)
                if section_array.dtype != np.int64:
                    try:
                        section_array = section_array.astype(np.int64, copy=False)
                    except TypeError, ValueError:
                        pass
                new_channel_values.values.longlong_array.values[:] = section_array
            elif channel_datatype == ods.DataTypeEnum.DT_FLOAT:
                new_channel_values.values.float_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_DOUBLE:
                new_channel_values.values.double_array.values[:] = section
            elif channel_datatype == ods.DataTypeEnum.DT_COMPLEX:
                real_values: list[float] = []
                for complex_value in section:
                    real_values.append(complex_value.real)
                    real_values.append(complex_value.imag)
                new_channel_values.values.float_array.values[:] = real_values
            elif channel_datatype == ods.DataTypeEnum.DT_DCOMPLEX:
                real_values_d: list[float] = []
                for complex_value in section:
                    real_values_d.append(complex_value.real)
                    real_values_d.append(complex_value.imag)
                new_channel_values.values.double_array.values[:] = real_values_d
            elif channel_datatype == ods.DataTypeEnum.DT_STRING:
                ExternalDataFile._assign_strings(new_channel_values.values.string_array, section, channel)
            elif channel_datatype == ods.DataTypeEnum.DT_BYTESTR:
                for item in section:
                    new_channel_values.values.bytestr_array.values.append(item.tobytes())
            else:
                raise NotImplementedError(
                    f"Unknown np datatype {section.dtype} for type {channel_datatype} in {mdf4.name.name}!"
                )

            rv.channels.append(new_channel_values)

        self._log.debug("GetValues returning %d channels", len(rv.channels))
        return rv

    @staticmethod
    def _assign_strings(target: ods.StringArray, section: np.ndarray, channel: Any) -> None:
        if section.dtype.kind == "S":
            if channel.data_type == 6:
                # Latin-1 (ISO-8859-1) encoding
                target.values[:] = ExternalDataFile._latin1_decoder(section).tolist()
                return
            elif channel.data_type == 7:
                # UTF-8 encoding
                target.values[:] = ExternalDataFile._utf8_decoder(section).tolist()
                return
            elif channel.data_type == 8:
                # UTF-16 little-endian encoding
                target.values[:] = ExternalDataFile._utf16le_decoder(section).tolist()
                return
            elif channel.data_type == 9:
                # UTF-16 big-endian encoding
                target.values[:] = ExternalDataFile._utf16be_decoder(section).tolist()
                return

        values: list[str] = []
        for item in np.asarray(section).ravel():
            if isinstance(item, (bytes, bytearray, np.bytes_)):
                values.append(item.decode("utf-8") if item else "")
            else:
                values.append(str(item))

        target.values[:] = np.asarray(values, dtype=str)

    def __add_file_header(self, header: HeaderBlock | None, attributes: Any) -> None:
        if header is None:
            return

        if header.description is not None:
            attributes.variables["description"].string_array.values.append(header.description)

        if header._common_properties is not None:

            def add_attributes(prefix: str | None, properties: dict[str, Any]) -> None:
                for key, value in properties.items():
                    entry = f"{prefix}~{key}" if prefix is not None else key
                    if isinstance(value, dict):
                        add_attributes(entry, value)
                    else:
                        attributes.variables[entry].string_array.values.append(str(value))

            add_attributes(None, header._common_properties)

    def __get_channel_data_type(self, channel: Channel) -> ods.DataTypeEnum:
        rv = self.__get_channel_data_type_base(channel)
        if channel.conversion is not None:
            rv = self.__get_conversion_data_type(rv, channel.conversion)
        return rv

    def __get_conversion_data_type(
        self, rv: ods.DataTypeEnum, conversion: ChannelConversion | None
    ) -> ods.DataTypeEnum:
        if conversion is not None:
            if ods.DataTypeEnum.DT_STRING == rv:
                if 9 == conversion.conversion_type:
                    # text to value tabular look-up
                    return ods.DataTypeEnum.DT_DOUBLE
            elif conversion.conversion_type in [1, 2, 3, 4, 5]:
                return ods.DataTypeEnum.DT_DOUBLE
            elif conversion.conversion_type in [7, 8] and not self.values_ignore_value2text_conversions:
                if conversion.flags & 4 and conversion.referenced_blocks is not None:
                    # Status string flag is set
                    # the actual conversion rule is given in CCBLOCK referenced by default value.
                    return self.__get_conversion_data_type(rv, conversion.referenced_blocks.get("default_addr"))  # type: ignore
                return ods.DataTypeEnum.DT_STRING
        return rv

    def __get_channel_data_type_base(self, channel: Channel) -> ods.DataTypeEnum:
        # [width="100",options="header"]
        # |====================
        # | number | cn_bit_count | DataTypeEnum | description
        # | _Integer data types:_ | | |
        # | 0, 1   | 1           | DT_BOOLEAN  | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 2 - 8       | DT_BYTE     | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 8 - 15      | DT_SHORT    | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 16 - 31     | DT_LONG     | unsigned integer (LE Byte order, BE Byte order)
        # | 0, 1   | 32 - 63     | DT_LONGLONG | unsigned integer (LE Byte order, BE Byte order)
        # | 2, 3   | 64 - 64     | DT_DOUBLE   | signed integer (LE Byte order, BE Byte order)
        # | 2, 3   | 1           | DT_BOOLEAN  | signed integer (LE Byte order, BE Byte order)
        # | 2, 3   | 2 - 16      | DT_SHORT    | signed integer (LE Byte order, BE Byte order)
        # | 2, 3   | 17 - 32     | DT_LONG     | signed integer (LE Byte order, BE Byte order)
        # | 2, 3   | 33 - 64     | DT_LONGLONG | signed integer (LE Byte order, BE Byte order)
        # | _Floating-point data types:_ | | |
        # | 4, 5   | 16, 32      | DT_FLOAT    | IEEE 754 floating-point (LE Byte order, BE Byte order)
        # | 4, 5   | 64          | DT_DOUBLE   | IEEE 754 floating-point (LE Byte order, BE Byte order)
        # | _String data types:_ | | |
        # | 6      |             | DT_STRING   | string (SBC, ISO-8859-1 encoded, NULL terminated)
        # | 7      |             | DT_STRING   | string (UTF-8 encoded, NULL terminated)
        # | 8      |             | DT_STRING   | string (UTF-16 encoded LE, NULL terminated)
        # | 9      |             | DT_STRING   | string (UTF-16 encoded BE, NULL terminated)
        # | _Complex data types:_ | | |
        # | 10     |             | DT_BYTESTR  | byte array with unknown content (e.g. structure)
        # | 11     |             | DT_BYTESTR  | MIME sample
        # | 12     |             | DT_BYTESTR  | MIME stream
        # | 13     |             | DT_DATE     | CANopen date
        # | 14     |             | DT_DATE     | CANopen time
        # | 15, 16 | 16, 32, 64  | DT_COMPLEX  | complex number
        # | 15, 16 | 128         | DT_DCOMPLEX | complex number
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
            if 1 <= mdf4_data_bit_count <= 64:
                return ods.DataTypeEnum.DT_COMPLEX
            if 65 <= mdf4_data_bit_count <= 128:
                return ods.DataTypeEnum.DT_DCOMPLEX

        return ods.DataTypeEnum.DT_DOUBLE


def main() -> None:
    """Run plugin server entry point."""
    from ods_exd_api_box import serve_plugin

    serve_plugin(file_type_name="MDF4", file_type_factory=ExternalDataFile.create, file_type_file_patterns=["*.mf4"])


if __name__ == "__main__":
    main()
