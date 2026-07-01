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
