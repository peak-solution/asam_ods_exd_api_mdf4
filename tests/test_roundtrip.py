"""Roundtrip tests: write MDF4 files with asammdf, read back via ExternalDataFile, verify.

Each test writes one or more MDF4 files into a TemporaryDirectory, opens them
through the ExdFileInterface / ExternalDataReader and checks that the returned
structure and values match exactly what was written.

Data-type mapping quirks tested explicitly:
  uint8  (8-bit unsigned)  → DT_BYTE      (byte_array)
  uint16 (16-bit unsigned) → DT_LONG      (long_array)
  uint32 (32-bit unsigned) → DT_LONGLONG  (longlong_array)
  uint64 (64-bit unsigned) → DT_DOUBLE    (double_array)  ← special case
  int8   (8-bit signed)    → DT_SHORT     (long_array)
  int16  (16-bit signed)   → DT_SHORT     (long_array)
  int32  (32-bit signed)   → DT_LONG      (long_array)
  int64  (64-bit signed)   → DT_LONGLONG  (longlong_array)
  float32                  → DT_FLOAT     (float_array)
  float64                  → DT_DOUBLE    (double_array)
  complex64                → DT_COMPLEX   (float_array, interleaved re/im)
  complex128               → DT_DCOMPLEX  (double_array, interleaved re/im)
  string (utf-8)           → DT_STRING    (string_array)
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np
from asammdf import MDF, Signal
from ods_exd_api_box import ExternalDataReader, FileHandlerRegistry, exd_api, ods

from external_data_file import ExternalDataFile

# pylint: disable=E1101


def _uri(path: str) -> str:
    return Path(path).resolve().as_uri()


class TestRoundtrip(unittest.TestCase):
    """Write MDF4 via asammdf, read back through ExternalDataFile, assert correctness."""

    def setUp(self):
        FileHandlerRegistry.register(file_type_name="test", factory=ExternalDataFile)
        self.service = ExternalDataReader()
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save(self, mdf: MDF, name: str) -> str:
        """Save *mdf* to a temp file and return the path."""
        path = os.path.join(self.tmp_dir, name)
        mdf.save(path, compression=2, overwrite=True)
        return path

    def _make_file(
        self, signals: list, name: str, *, start_time=None, group_comment: str = "", acq_name: str = ""
    ) -> str:
        """Create a single-group MDF4 file from *signals* and return its path."""
        with MDF(version="4.10") as mdf:
            if start_time is not None:
                mdf.start_time = start_time
            mdf.append(signals, comment=group_comment, acq_name=acq_name, common_timebase=True)
            return self._save(mdf, name)

    def _open(self, path: str):
        return self.service.Open(exd_api.Identifier(url=_uri(path), parameters=""), None)

    def _structure(self, handle) -> exd_api.StructureResult:
        return cast(exd_api.StructureResult, self.service.GetStructure(exd_api.StructureRequest(handle=handle), None))

    def _values(
        self, handle, group_id: int, channel_ids: list, start: int = 0, limit: int = 9999, context=None
    ) -> exd_api.ValuesResult:
        return cast(
            exd_api.ValuesResult,
            self.service.GetValues(
                exd_api.ValuesRequest(
                    handle=handle, group_id=group_id, channel_ids=channel_ids, start=start, limit=limit
                ),
                context,
            ),
        )

    def _assert_floats(self, actual, expected, places: int = 5):
        self.assertEqual(len(actual), len(expected), f"length mismatch: got {len(actual)}, want {len(expected)}")
        for i, (a, e) in enumerate(zip(actual, expected)):
            self.assertAlmostEqual(float(a), float(e), places=places, msg=f"index {i}: {a} != {e}")

    def _decode_string_samples(self, samples: np.ndarray, encoding: str) -> list[str]:
        decoded = []
        for item in samples:
            payload = bytes(item).rstrip(b"\x00")
            if encoding.startswith("utf-16") and len(payload) % 2 != 0:
                payload += b"\x00"
            decoded.append(payload.decode(encoding))
        return decoded

    # ==================================================================
    # Scalar numeric types
    # ==================================================================

    def test_float64_roundtrip(self):
        vals = np.array([1.1, 2.2, -3.3], np.float64)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_f64", unit="m/s")
        path = self._make_file([sig], "f64.mf4")
        handle = self._open(path)
        try:
            structure = self._structure(handle)
            ch = structure.groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_DOUBLE)
            self.assertEqual(ch.unit_string, "m/s")
            result = self._values(handle, 0, [1])
            self._assert_floats(result.channels[0].values.double_array.values, vals)
        finally:
            self.service.Close(handle, None)

    def test_float32_roundtrip(self):
        vals = np.array([1.5, -2.25, 0.0], np.float32)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_f32", unit="V")
        path = self._make_file([sig], "f32.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_FLOAT)
            result = self._values(handle, 0, [1])
            self._assert_floats(result.channels[0].values.float_array.values, vals.tolist())
        finally:
            self.service.Close(handle, None)

    def test_int8_roundtrip(self):
        """int8 (signed 8-bit) → DT_SHORT / long_array."""
        vals = np.array([-128, 0, 127], np.int8)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_i8")
        path = self._make_file([sig], "i8.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_SHORT)
            result = self._values(handle, 0, [1])
            self.assertSequenceEqual(list(result.channels[0].values.long_array.values), vals.tolist())
        finally:
            self.service.Close(handle, None)

    def test_uint8_roundtrip(self):
        """uint8 (unsigned 8-bit) → DT_BYTE / byte_array."""
        vals = np.array([0, 128, 255], np.uint8)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_u8")
        path = self._make_file([sig], "u8.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_BYTE)
            result = self._values(handle, 0, [1])
            # byte_array.values is a bytes object; list() gives ints 0-255
            self.assertSequenceEqual(list(result.channels[0].values.byte_array.values), vals.tolist())
        finally:
            self.service.Close(handle, None)

    def test_int16_roundtrip(self):
        """int16 (signed 16-bit) → DT_SHORT / long_array."""
        vals = np.array([-1000, 0, 1000], np.int16)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_i16")
        path = self._make_file([sig], "i16.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_SHORT)
            result = self._values(handle, 0, [1])
            self.assertSequenceEqual(list(result.channels[0].values.long_array.values), vals.tolist())
        finally:
            self.service.Close(handle, None)

    def test_uint16_roundtrip(self):
        """uint16 (unsigned 16-bit, bit_count=16) → DT_LONG / long_array."""
        vals = np.array([0, 1000, 65535], np.uint16)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_u16")
        path = self._make_file([sig], "u16.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_LONG)
            result = self._values(handle, 0, [1])
            self.assertSequenceEqual(list(result.channels[0].values.long_array.values), vals.tolist())
        finally:
            self.service.Close(handle, None)

    def test_int32_roundtrip(self):
        """int32 (signed 32-bit) → DT_LONG / long_array."""
        vals = np.array([-100000, 0, 100000], np.int32)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_i32", unit="rpm")
        path = self._make_file([sig], "i32.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_LONG)
            result = self._values(handle, 0, [1])
            self.assertSequenceEqual(list(result.channels[0].values.long_array.values), vals.tolist())
        finally:
            self.service.Close(handle, None)

    def test_uint32_roundtrip(self):
        """uint32 (unsigned 32-bit, bit_count=32) → DT_LONGLONG / longlong_array."""
        vals = np.array([0, 50000, 4294967295], np.uint32)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_u32")
        path = self._make_file([sig], "u32.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_LONGLONG)
            result = self._values(handle, 0, [1])
            self.assertSequenceEqual(list(result.channels[0].values.longlong_array.values), [int(v) for v in vals])
        finally:
            self.service.Close(handle, None)

    def test_int64_roundtrip(self):
        """int64 (signed 64-bit) → DT_LONGLONG / longlong_array."""
        vals = np.array([-(2**40), 0, 2**40], np.int64)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_i64", unit="ns")
        path = self._make_file([sig], "i64.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_LONGLONG)
            result = self._values(handle, 0, [1])
            self.assertSequenceEqual(list(result.channels[0].values.longlong_array.values), vals.tolist())
        finally:
            self.service.Close(handle, None)

    def test_uint64_roundtrip(self):
        """uint64 (unsigned 64-bit, bit_count=64) → DT_DOUBLE / double_array.

        The mapping table treats 64-bit unsigned as DT_DOUBLE because the
        bit_count=64 falls in the unsigned 64-64 → DT_DOUBLE branch.
        """
        vals = np.array([0, 2**32, 2**52], np.uint64)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_u64")
        path = self._make_file([sig], "u64.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_DOUBLE)
            result = self._values(handle, 0, [1])
            self._assert_floats(result.channels[0].values.double_array.values, [float(v) for v in vals])
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # String
    # ==================================================================

    def test_string_utf8_roundtrip(self):
        vals = ["hello", "world", "αβγ"]
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch_str", unit="", encoding="utf-8")
        path = self._make_file([sig], "str.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_STRING)
            result = self._values(handle, 0, [1])
            self.assertSequenceEqual(list(result.channels[0].values.string_array.values), vals)
        finally:
            self.service.Close(handle, None)

    def test_assign_strings_decodes_mdf_string_encodings(self):
        cases = [
            (6, "latin-1", ["Grüße", "façade"]),
            (7, "utf-8", ["Grüße", "αβγ"]),
            (8, "utf-16-le", ["Grüße", "漢字"]),
            (9, "utf-16-be", ["Grüße", "漢字"]),
        ]

        for data_type, encoding, values in cases:
            with self.subTest(data_type=data_type, encoding=encoding):
                target = ods.StringArray()
                section = np.array([value.encode(encoding).rstrip(b"\x00") for value in values])
                channel = SimpleNamespace(data_type=data_type)

                ExternalDataFile._assign_strings(target, section, channel)

                self.assertSequenceEqual(list(target.values), values)

    def test_string_multiencoding_roundtrip(self):
        ts = [0.0, 1.0]
        expected_values = [
            ["Grüße", "façade"],
            ["Grüße", "αβγ"],
            ["Grüße", "漢字"],
            ["Grüße", "漢字"],
        ]
        expected_data_types = [6, 7, 8, 9]
        encodings = ["latin-1", "utf-8", "utf-16-le", "utf-16-be"]
        sigs = [
            Signal(samples=expected_values[0], timestamps=ts, name="latin1", encoding="latin-1"),
            Signal(samples=expected_values[1], timestamps=ts, name="utf8", encoding="utf-8"),
            Signal(samples=expected_values[2], timestamps=ts, name="utf16le", encoding="utf-16-le"),
            Signal(samples=expected_values[3], timestamps=ts, name="utf16be", encoding="utf-16-be"),
        ]
        path = self._make_file(sigs, "strings_multi_encoding.mf4")

        with MDF(path) as mdf:
            channels = mdf.groups[0].channels[1:]
            self.assertEqual([channel.data_type for channel in channels], expected_data_types)

            signals = mdf.select([(None, 0, channel_id) for channel_id in [1, 2, 3, 4]], raw=False, copy_master=False)
            for signal, expected, encoding in zip(signals, expected_values, encodings):
                self.assertEqual(signal.samples.dtype.kind, "S")
                decoded = []
                for item in signal.samples:
                    payload = bytes(item)
                    if encoding.startswith("utf-16") and len(payload) % 2 != 0:
                        payload += b"\x00"
                    decoded.append(payload.decode(encoding))
                self.assertSequenceEqual(decoded, expected)

        handle = self._open(path)
        try:
            channels = self._structure(handle).groups[0].channels
            self.assertEqual(len(channels), 5)
            for channel in channels[1:]:
                self.assertEqual(channel.data_type, ods.DataTypeEnum.DT_STRING)

            result = self._values(handle, 0, [1, 2, 3, 4])
            self.assertEqual([channel.id for channel in result.channels], [1, 2, 3, 4])
            for channel_result, expected in zip(result.channels, expected_values):
                self.assertSequenceEqual(list(channel_result.values.string_array.values), expected)
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Complex
    # ==================================================================

    def test_complex64_roundtrip(self):
        """complex64 → DT_COMPLEX; values stored interleaved re0,im0,re1,im1."""
        vals = np.array([1 + 2j, 3 + 4j], np.complex64)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0], name="ch_c64")
        path = self._make_file([sig], "c64.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_COMPLEX)
            result = self._values(handle, 0, [1])
            self._assert_floats(result.channels[0].values.float_array.values, [1.0, 2.0, 3.0, 4.0])
        finally:
            self.service.Close(handle, None)

    def test_complex128_roundtrip(self):
        """complex128 → DT_DCOMPLEX; values stored interleaved re0,im0,re1,im1."""
        vals = np.array([5 + 6j, 7 + 8j], np.complex128)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0], name="ch_c128")
        path = self._make_file([sig], "c128.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_DCOMPLEX)
            result = self._values(handle, 0, [1])
            self._assert_floats(result.channels[0].values.double_array.values, [5.0, 6.0, 7.0, 8.0])
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Linear conversion → DT_DOUBLE
    # ==================================================================

    def test_linear_conversion_yields_double(self):
        """A channel with a linear conversion (type 1) must report DT_DOUBLE
        and return the converted (not raw) values."""
        # asammdf applies conversion on read (raw=False), so values become float
        sig = Signal(
            samples=np.array([0, 1, 2], np.int32),
            timestamps=[0.0, 1.0, 2.0],
            name="ch_lin",
            conversion={"conversion_type": 1, "a": 2.5, "b": 0.5},
        )
        path = self._make_file([sig], "linear.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.data_type, ods.DataTypeEnum.DT_DOUBLE)
            result = self._values(handle, 0, [1])
            # y = 2.5*x + 0.5  →  0.5, 3.0, 5.5
            self._assert_floats(result.channels[0].values.double_array.values, [0.5, 3.0, 5.5])
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Multiple groups / channels
    # ==================================================================

    def test_multiple_groups_roundtrip(self):
        """Values from different groups must be addressed by their group_id."""
        ts = [0.0, 1.0, 2.0]
        with MDF(version="4.10") as mdf:
            mdf.append(
                [Signal(samples=np.array([1.0, 2.0, 3.0], np.float64), timestamps=ts, name="g0_ch")],
                comment="grp0",
                common_timebase=True,
            )
            mdf.append(
                [Signal(samples=np.array([10, 20, 30], np.int32), timestamps=ts, name="g1_ch")],
                comment="grp1",
                common_timebase=True,
            )
            path = self._save(mdf, "multigrp.mf4")
        handle = self._open(path)
        try:
            structure = self._structure(handle)
            self.assertEqual(len(structure.groups), 2)
            self.assertEqual(structure.groups[0].id, 0)
            self.assertEqual(structure.groups[1].id, 1)

            r0 = self._values(handle, 0, [1])
            self._assert_floats(r0.channels[0].values.double_array.values, [1.0, 2.0, 3.0])

            r1 = self._values(handle, 1, [1])
            self.assertSequenceEqual(list(r1.channels[0].values.long_array.values), [10, 20, 30])
        finally:
            self.service.Close(handle, None)

    def test_multiple_channels_roundtrip(self):
        """All channels in a group must be individually addressable."""
        ts = [0.0, 1.0, 2.0]
        sigs = [
            Signal(samples=np.array([1.0, 2.0, 3.0], np.float64), timestamps=ts, name="ch_a"),
            Signal(samples=np.array([4, 5, 6], np.int32), timestamps=ts, name="ch_b"),
            Signal(samples=["x", "y", "z"], timestamps=ts, name="ch_c", encoding="utf-8"),
        ]
        path = self._make_file(sigs, "multichan.mf4")
        handle = self._open(path)
        try:
            structure = self._structure(handle)
            # time (ch0) + 3 data channels
            self.assertEqual(len(structure.groups[0].channels), 4)

            result = self._values(handle, 0, [1, 2, 3])
            self.assertEqual(len(result.channels), 3)
            self._assert_floats(result.channels[0].values.double_array.values, [1.0, 2.0, 3.0])
            self.assertSequenceEqual(list(result.channels[1].values.long_array.values), [4, 5, 6])
            self.assertSequenceEqual(list(result.channels[2].values.string_array.values), ["x", "y", "z"])
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Paging: start / limit
    # ==================================================================

    def test_paging_middle_slice(self):
        """Reading a slice from the middle of a channel must return only those rows."""
        n = 50
        vals = np.arange(n, dtype=np.float64)
        sig = Signal(samples=vals, timestamps=np.arange(n, dtype=np.float64), name="ramp")
        path = self._make_file([sig], "paging.mf4")
        handle = self._open(path)
        try:
            result = self._values(handle, 0, [1], start=10, limit=5)
            self._assert_floats(result.channels[0].values.double_array.values, list(vals[10:15]))
        finally:
            self.service.Close(handle, None)

    def test_paging_limit_clamps_at_end(self):
        """A limit larger than the remaining rows must silently return what exists."""
        vals = np.array([1.0, 2.0, 3.0], np.float64)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch")
        path = self._make_file([sig], "clamp.mf4")
        handle = self._open(path)
        try:
            result = self._values(handle, 0, [1], start=0, limit=9999)
            self.assertEqual(len(result.channels[0].values.double_array.values), 3)
        finally:
            self.service.Close(handle, None)

    def test_paging_first_row_only(self):
        vals = np.array([10.0, 20.0, 30.0], np.float64)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch")
        path = self._make_file([sig], "first.mf4")
        handle = self._open(path)
        try:
            result = self._values(handle, 0, [1], start=0, limit=1)
            self._assert_floats(result.channels[0].values.double_array.values, [10.0])
        finally:
            self.service.Close(handle, None)

    def test_paging_last_row(self):
        vals = np.array([10.0, 20.0, 30.0], np.float64)
        sig = Signal(samples=vals, timestamps=[0.0, 1.0, 2.0], name="ch")
        path = self._make_file([sig], "last.mf4")
        handle = self._open(path)
        try:
            result = self._values(handle, 0, [1], start=2, limit=1)
            self._assert_floats(result.channels[0].values.double_array.values, [30.0])
        finally:
            self.service.Close(handle, None)

    def test_paging_multiple_channels_same_slice(self):
        """When requesting multiple channels with start/limit,
        every channel must return the same slice."""
        n = 20
        ts = np.arange(n, dtype=np.float64)
        sigs = [
            Signal(samples=np.arange(n, dtype=np.float64) * 1.0, timestamps=ts, name="a"),
            Signal(samples=np.arange(n, dtype=np.int32) * 2, timestamps=ts, name="b"),
        ]
        path = self._make_file(sigs, "slice_multi.mf4")
        handle = self._open(path)
        try:
            result = self._values(handle, 0, [1, 2], start=5, limit=4)
            self._assert_floats(result.channels[0].values.double_array.values, [5.0, 6.0, 7.0, 8.0])
            self.assertSequenceEqual(list(result.channels[1].values.long_array.values), [10, 12, 14, 16])
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Edge cases: single row / empty group
    # ==================================================================

    def test_single_row_roundtrip(self):
        sig = Signal(samples=np.array([42.0], np.float64), timestamps=[0.0], name="ch")
        path = self._make_file([sig], "single.mf4")
        handle = self._open(path)
        try:
            self.assertEqual(self._structure(handle).groups[0].number_of_rows, 1)
            result = self._values(handle, 0, [1])
            self._assert_floats(result.channels[0].values.double_array.values, [42.0])
        finally:
            self.service.Close(handle, None)

    def test_empty_group_structure(self):
        """A group with zero rows must be reported with number_of_rows == 0."""
        sig = Signal(samples=np.array([], np.float64), timestamps=np.array([]), name="empty_ch")
        path = self._make_file([sig], "empty.mf4")
        handle = self._open(path)
        try:
            structure = self._structure(handle)
            self.assertEqual(structure.groups[0].number_of_rows, 0)
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Channel metadata
    # ==================================================================

    def test_channel_unit_and_description(self):
        sig = Signal(
            samples=np.array([1.0, 2.0], np.float64),
            timestamps=[0.0, 1.0],
            name="speed",
            unit="km/h",
            comment="vehicle speed",
        )
        path = self._make_file([sig], "ch_meta.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertEqual(ch.unit_string, "km/h")
            self.assertEqual(ch.attributes.variables["description"].string_array.values[0], "vehicle speed")
        finally:
            self.service.Close(handle, None)

    def test_channel_without_description_has_no_attribute(self):
        """Channels with no comment must not have a 'description' attribute."""
        sig = Signal(samples=np.array([1.0], np.float64), timestamps=[0.0], name="no_comment")
        path = self._make_file([sig], "no_desc.mf4")
        handle = self._open(path)
        try:
            ch = self._structure(handle).groups[0].channels[1]
            self.assertNotIn("description", ch.attributes.variables)
        finally:
            self.service.Close(handle, None)

    def test_first_channel_is_independent(self):
        """Channel 0 (time axis) must carry independent=1; data channels must not."""
        sig = Signal(samples=np.array([1.0, 2.0], np.float64), timestamps=[0.0, 1.0], name="ch")
        path = self._make_file([sig], "indep.mf4")
        handle = self._open(path)
        try:
            grp = self._structure(handle).groups[0]
            time_ch = grp.channels[0]
            self.assertIn("independent", time_ch.attributes.variables)
            self.assertEqual(time_ch.attributes.variables["independent"].long_array.values[0], 1)
            data_ch = grp.channels[1]
            self.assertNotIn("independent", data_ch.attributes.variables)
        finally:
            self.service.Close(handle, None)

    def test_time_channel_values(self):
        """Reading channel 0 (independent) must return the timestamps."""
        ts = [0.0, 0.5, 1.0]
        sig = Signal(samples=np.array([10.0, 20.0, 30.0], np.float64), timestamps=ts, name="ch")
        path = self._make_file([sig], "time_vals.mf4")
        handle = self._open(path)
        try:
            result = self._values(handle, 0, [0])
            self.assertEqual(result.channels[0].values.data_type, ods.DataTypeEnum.DT_DOUBLE)
            self._assert_floats(result.channels[0].values.double_array.values, ts)
        finally:
            self.service.Close(handle, None)

    def test_virtual_master_channel(self):
        """A virtual master channel (channel_type=3) must be marked independent and
        return sample indices [0, 1, 2, ...] as DT_DOUBLE values."""
        vals = np.array([10.0, 20.0, 30.0], np.float64)
        sig = Signal(samples=vals, timestamps=[0.5, 1.5, 3.0], name="speed", unit="m/s")
        with MDF(version="4.10") as mdf:
            mdf.append([sig], common_timebase=True)
            mdf.groups[0].channels[0].channel_type = 3  # VIRTUAL_MASTER
            path = self._save(mdf, "virtual_master.mf4")
        handle = self._open(path)
        try:
            structure = self._structure(handle)
            grp = structure.groups[0]
            time_ch = grp.channels[0]
            self.assertEqual(time_ch.name, "time")
            self.assertIn("independent", time_ch.attributes.variables)
            self.assertEqual(time_ch.attributes.variables["independent"].long_array.values[0], 1)
            self.assertEqual(time_ch.data_type, ods.DataTypeEnum.DT_DOUBLE)

            data_ch = grp.channels[1]
            self.assertNotIn("independent", data_ch.attributes.variables)

            # Virtual master yields sample indices as doubles
            result = self._values(handle, 0, [0, 1])
            self._assert_floats(result.channels[0].values.double_array.values, [0.0, 1.0, 2.0])
            self._assert_floats(result.channels[1].values.double_array.values, vals.tolist())
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Group metadata
    # ==================================================================

    def test_group_name_and_description(self):
        sig = Signal(samples=np.array([1.0], np.float64), timestamps=[0.0], name="ch")
        path = self._make_file([sig], "grp_meta.mf4", group_comment="my_comment", acq_name="my_group")
        handle = self._open(path)
        try:
            grp = self._structure(handle).groups[0]
            self.assertEqual(grp.name, "my_group")
            self.assertEqual(grp.attributes.variables["description"].string_array.values[0], "my_comment")
        finally:
            self.service.Close(handle, None)

    def test_group_measurement_begin_matches_file_start_time(self):
        start = datetime(2024, 3, 15, 9, 0, 0)
        sig = Signal(samples=np.array([1.0], np.float64), timestamps=[0.0], name="ch")
        path = self._make_file([sig], "meas_begin.mf4", start_time=start)
        handle = self._open(path)
        try:
            expected = start.strftime("%Y%m%d%H%M%S%f")
            structure = self._structure(handle)
            self.assertEqual(structure.attributes.variables["start_time"].string_array.values[0], expected)
            self.assertEqual(
                structure.groups[0].attributes.variables["measurement_begin"].string_array.values[0], expected
            )
        finally:
            self.service.Close(handle, None)

    def test_total_number_of_channels(self):
        ts = [0.0, 1.0]
        sigs = [Signal(samples=np.array([float(i)] * 2, np.float64), timestamps=ts, name=f"ch{i}") for i in range(5)]
        path = self._make_file(sigs, "total_ch.mf4")
        handle = self._open(path)
        try:
            grp = self._structure(handle).groups[0]
            # 5 data channels + 1 implicit time channel
            self.assertEqual(grp.total_number_of_channels, 6)
            self.assertEqual(len(grp.channels), 6)
        finally:
            self.service.Close(handle, None)

    def test_structure_identifier_url_is_set(self):
        sig = Signal(samples=np.array([1.0], np.float64), timestamps=[0.0], name="ch")
        path = self._make_file([sig], "url.mf4")
        handle = self._open(path)
        try:
            self.assertNotEqual(self._structure(handle).identifier.url, "")
        finally:
            self.service.Close(handle, None)

    def test_values_result_carries_group_id(self):
        """ValuesResult.id must equal the requested group_id."""
        ts = [0.0, 1.0]
        with MDF(version="4.10") as mdf:
            for i in range(3):
                mdf.append(
                    [Signal(samples=np.array([float(i)] * 2, np.float64), timestamps=ts, name="ch")],
                    common_timebase=True,
                )
            path = self._save(mdf, "grp_id.mf4")
        handle = self._open(path)
        try:
            for gid in range(3):
                result = self._values(handle, gid, [1])
                self.assertEqual(result.id, gid)
        finally:
            self.service.Close(handle, None)

    # ==================================================================
    # Error cases
    # ==================================================================

    def test_invalid_group_id_raises(self):
        """Requesting a non-existent group_id must raise ValueError."""
        sig = Signal(samples=np.array([1.0], np.float64), timestamps=[0.0], name="ch")
        path = self._make_file([sig], "err_grp.mf4")
        handle = self._open(path)
        try:
            with self.assertRaises(ValueError):
                self._values(handle, 999, [0])
        finally:
            self.service.Close(handle, None)

    def test_invalid_channel_id_raises(self):
        """Requesting a non-existent channel_id must raise ValueError."""
        sig = Signal(samples=np.array([1.0], np.float64), timestamps=[0.0], name="ch")
        path = self._make_file([sig], "err_ch.mf4")
        handle = self._open(path)
        try:
            with self.assertRaises(ValueError):
                self._values(handle, 0, [999])
        finally:
            self.service.Close(handle, None)

    def test_start_beyond_row_count_raises(self):
        """A start index past the last row must raise ValueError."""
        sig = Signal(samples=np.array([1.0, 2.0], np.float64), timestamps=[0.0, 1.0], name="ch")
        path = self._make_file([sig], "err_start.mf4")
        handle = self._open(path)
        try:
            with self.assertRaises(ValueError):
                self._values(handle, 0, [1], start=999)
        finally:
            self.service.Close(handle, None)
