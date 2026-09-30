#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据源插件机制的用例：注册表、目录扫描、坏插件隔离，以及 JP18 插件本身。

用**合成日志**而不是真实设备日志：用例必须在任何机器上都能跑。
插件是外面送进来的代码，所以"它坏了会怎样"和"它正常时对不对"一样重要。

在仓库根运行：python -m unittest discover -s backend/tests -t . -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.contract import validate
from backend.sources import get_plugin, list_plugins, load_directory, load_warnings
from backend.sources import registry

SAMPLES_PER_PACKET = 66
FILL = b"\x80\x80\x80"


def make_packet(samples: list[int]) -> bytes:
    """按真实格式造一个子包：0x88 + 66 组 3 字节 + 末尾 4 字节。"""
    body = b"".join(value.to_bytes(3, "big", signed=True) for value in samples)
    body += FILL * (SAMPLES_PER_PACKET - len(samples))
    return b"\x88" + body + b"\x00\x02\x80\xA0"


def write_log(path: Path, packets: list[bytes]) -> None:
    raw = b"".join(packets)
    path.write_text(" ".join(f"{byte:02X}" for byte in raw), encoding="utf-8")


def write_plugin(root: Path, name: str, manifest: dict, code: str) -> None:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (directory / "plugin.py").write_text(code, encoding="utf-8")


class RegistryTest(unittest.TestCase):
    def test_builtin_plugin_is_registered(self):
        self.assertIn("contract-json", [plugin.id for plugin in list_plugins()])

    def test_repository_plugin_directory_loads(self):
        load_directory()
        plugin = get_plugin("jp18-ecg")
        self.assertEqual("oneshot", plugin.mode)
        self.assertTrue(plugin.declare_params())

    def test_rescanning_the_same_directory_is_silent(self):
        load_directory()
        self.assertEqual([], load_directory())

    def test_unknown_plugin_lists_available_ones(self):
        with self.assertRaises(ValueError) as ctx:
            get_plugin("没这个插件")
        self.assertIn("contract-json", str(ctx.exception))

    def test_broken_plugin_does_not_break_the_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_plugin(
                root,
                "broken",
                {"id": "broken", "display_name": "坏插件", "version": "1.0.0", "entry": "plugin.py"},
                "raise RuntimeError('加载就炸')\n",
            )
            write_plugin(
                root,
                "good",
                {"id": "test-good", "display_name": "好插件", "version": "1.0.0", "entry": "plugin.py"},
                "def extract(path, options):\n    return {'ok': True}\n\n\ndef declare_params():\n    return []\n",
            )
            warnings = load_directory(root)

        self.addCleanup(registry._PLUGINS.pop, "test-good", None)
        self.assertIn("test-good", [plugin.id for plugin in list_plugins()])
        self.assertTrue(any("broken" in message for message in warnings))
        self.assertTrue(any("加载失败" in message for message in warnings))

    def test_missing_manifest_and_missing_entry_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "no-manifest").mkdir()
            write_plugin(
                root,
                "no-entry",
                {"id": "no-entry", "display_name": "缺入口", "version": "1.0.0", "entry": "missing.py"},
                "",
            )
            warnings = load_directory(root)

        self.assertTrue(any("manifest.json" in message for message in warnings))
        self.assertTrue(any("入口文件不存在" in message for message in warnings))

    def test_warnings_are_exposed_for_the_interface(self):
        self.assertEqual(load_warnings(), load_warnings())


class Jp18PluginTest(unittest.TestCase):
    """JP18 插件：包结构、填充、横轴选择、结果可复现。"""

    @classmethod
    def setUpClass(cls):
        load_directory()
        cls.plugin = get_plugin("jp18-ecg")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "sample.txt"
        # 第一个子包满 66 个样本；第二个子包只有 30 个，其余用填充补齐
        write_log(
            self.path,
            [make_packet(list(range(1000, 1066))), make_packet(list(range(2000, 2030)))],
        )

    def extract(self, **options):
        return self.plugin.extract(str(self.path), options)

    def test_samples_are_parsed_in_order_with_fill_skipped(self):
        data = self.extract()
        values = data["series"][0]["y"]["data"]
        self.assertEqual(96, len(values))
        self.assertEqual(1000, values[0])
        self.assertEqual(1065, values[65])
        self.assertEqual(2000, values[66])
        self.assertEqual(2029, values[-1])

    def test_default_axis_is_sample_index(self):
        data = self.extract()
        axis = data["series"][0]["x"]
        self.assertEqual("sequence", axis["kind"])
        self.assertEqual("sample", axis["unit"])
        self.assertEqual([0, 95], [axis["data"][0], axis["data"][-1]])
        self.assertIn("采样序号", axis["display_name"])

    def test_sample_rate_converts_axis_to_milliseconds(self):
        data = self.extract(sample_rate=250)
        axis = data["series"][0]["x"]
        self.assertEqual("time", axis["kind"])
        self.assertEqual("ms", axis["unit"])
        self.assertEqual("start", axis["origin"])
        self.assertEqual(0.0, axis["data"][0])
        self.assertEqual(200.0, axis["data"][50])  # 50 / 250 Hz = 200 ms

    def test_output_passes_contract_validation(self):
        self.assertTrue(validate(self.extract()).ok)

    def test_meta_records_how_missing_pieces_were_handled(self):
        notes = self.extract()["meta"]["notes"]
        self.assertIn("采样序号", notes)
        self.assertIn("填充", notes)

    def test_result_is_reproducible(self):
        self.assertEqual(self.extract(), self.extract())

    def test_negative_values_survive(self):
        path = Path(self._tmp.name) / "negative.txt"
        write_log(path, [make_packet([-1000, -1, 8388607, -8388608])])
        values = self.plugin.extract(str(path), {})["series"][0]["y"]["data"]
        self.assertEqual([-1000, -1, 8388607, -8388608], values)

    def test_empty_file_gives_readable_error(self):
        path = Path(self._tmp.name) / "empty.txt"
        path.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self.plugin.extract(str(path), {})
        self.assertIn("没有十六进制字节", str(ctx.exception))

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.plugin.extract(str(Path(self._tmp.name) / "没有.txt"), {})


if __name__ == "__main__":
    unittest.main()
