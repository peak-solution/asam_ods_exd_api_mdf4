import unittest
from pathlib import Path

from asammdf import MDF


class TestAsammdfReader(unittest.TestCase):
    def test_cn_type(self):
        main_file_path = Path.joinpath(Path(__file__).parent.resolve(), "..", "data", "simple.mf4")

        with MDF(main_file_path) as mdf:
            for group in mdf.groups:
                for channel in group.channels:
                    self.assertIsNotNone(channel.name)
                    self.assertIsNotNone(channel.unit)

                    cn_type = channel.channel_type
                    print(f"Channel: {channel.name}, Type: {cn_type}")

                    assert (channel.name == "time" and cn_type == 2) or cn_type != 2

    def test_partial_string_mapping(self):
        main_file_path = Path.joinpath(
            Path(__file__).parent.resolve(), "..", "data", "examples", "PartialConversionValueRange2TextRational.mf4"
        )

        with MDF(main_file_path) as mdf:
            data = mdf.select(
                [(None, 0, channel_id) for channel_id in [0]],
                raw=False,
                ignore_value2text_conversions=False,
                record_offset=0,
                record_count=500,
                copy_master=False,
            )
            for signal_index, signal in enumerate(data, start=0):
                section = signal.samples
                print(f"***** {signal_index} {signal.name} *****")
                print(section)

            data2 = mdf.select(
                [(None, 0, channel_id) for channel_id in [0]],
                raw=False,
                ignore_value2text_conversions=False,
                record_offset=80,
                record_count=20,
                copy_master=False,
            )
            for signal_index, signal in enumerate(data2, start=0):
                section = signal.samples
                print(f"***** {signal_index} {signal.name} *****")
                print(section)

            data3 = mdf.select(
                [(None, 0, channel_id) for channel_id in [0]],
                raw=False,
                ignore_value2text_conversions=True,
                record_offset=80,
                record_count=20,
                copy_master=False,
            )
            for signal_index, signal in enumerate(data3, start=0):
                section = signal.samples
                print(f"***** {signal_index} {signal.name} *****")
                print(section)

            data4 = mdf.select(
                [(None, 0, channel_id) for channel_id in [0]],
                raw=True,
                ignore_value2text_conversions=False,
                record_offset=80,
                record_count=20,
                copy_master=False,
            )
            for signal_index, signal in enumerate(data4, start=0):
                section = signal.samples
                print(f"***** {signal_index} {signal.name} *****")
                print(section)

    def test_partial_string_demo(self):
        main_file_path = Path.joinpath(
            Path(__file__).parent.resolve(), "..", "data", "examples", "mdf4_demo_no_arrays.mf4"
        )

        with MDF(main_file_path) as mdf:
            for signal_index, signal in enumerate(
                mdf.select(
                    [(None, 0, channel_id) for channel_id in [8, 9, 10]],
                    raw=False,
                    ignore_value2text_conversions=False,
                    record_offset=0,
                    record_count=40,
                    copy_master=False,
                ),
                start=0,
            ):
                print(f"***** {signal_index} {signal.name} *****\n{signal.samples}")

            for signal_index, signal in enumerate(
                mdf.select(
                    [(None, 0, channel_id) for channel_id in [8, 9, 10]],
                    raw=False,
                    ignore_value2text_conversions=True,
                    record_offset=0,
                    record_count=40,
                    copy_master=False,
                ),
                start=0,
            ):
                print(f"***** {signal_index} {signal.name} *****\n{signal.samples}")
