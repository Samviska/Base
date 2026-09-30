#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""滤波用例：纯函数、边界窗口、缺失值、处理链的顺序与开关。

滤波最容易犯的三个错都在这份用例里盯着：
原地改输入（关掉滤波数据回不来）、边界窗口失真、参数变化不重算。

在仓库根运行：python -m unittest discover -s backend/tests -t . -v
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from backend.contract import validate
from backend.filters import apply_chain, chain_key, get_plugin, list_plugins, register
from backend.filters import chain as chain_module
from backend.filters.chain import FilterPlugin

EXAMPLES = Path(__file__).resolve().parents[2] / "contract" / "examples"


def dataset(xs: list, ys: list, name: str = "s") -> dict:
    return {
        "schema_version": "1.0",
        "meta": {"source": "t.log", "extractor": "t@1"},
        "series": [{"name": name, "unit": "1", "x": {"kind": "sequence", "data": xs}, "y": {"data": ys}}],
    }


def smooth(xs: list, ys: list, window: int) -> list:
    chain = [{"plugin": "moving-average", "enabled": True, "params": {"window": window}}]
    return apply_chain(dataset(xs, ys), chain)["series"][0]["y"]["data"]


def _scale(data: dict, params: dict) -> dict:
    factor = float(params.get("factor", 2))
    return {
        **data,
        "series": [
            {**s, "y": {**s["y"], "data": [None if v is None else v * factor for v in s["y"]["data"]]}}
            for s in data["series"]
        ],
    }


def _offset(data: dict, params: dict) -> dict:
    add = float(params.get("add", 1))
    return {
        **data,
        "series": [
            {**s, "y": {**s["y"], "data": [None if v is None else v + add for v in s["y"]["data"]]}}
            for s in data["series"]
        ],
    }


class MovingAverageTest(unittest.TestCase):
    def test_odd_window_is_centered_and_shrinks_at_edges(self):
        self.assertEqual([1.5, 2.0, 3.0, 4.0, 4.5], smooth(list(range(5)), [1, 2, 3, 4, 5], 3))

    def test_window_one_is_identity(self):
        self.assertEqual([1, 2, 3], smooth([0, 1, 2], [1, 2, 3], 1))

    def test_window_larger_than_data_averages_everything(self):
        result = smooth(list(range(4)), [1, 2, 3, 4], 1000)
        self.assertEqual([2.5, 2.5, 2.5, 2.5], result)

    def test_even_window_leans_left(self):
        self.assertEqual(
            [1.5, 2.0, 2.5, 3.5, 4.5, 5.0],
            smooth(list(range(6)), [1, 2, 3, 4, 5, 6], 4),
        )

    def test_null_in_window_makes_result_null(self):
        # 不拿周围的点凑一个假值：窗口内有缺失，结果就缺失（缺失会波及左右各半个窗口）
        self.assertEqual(
            [1.5, None, None, None, 4.5],
            smooth(list(range(5)), [1, 2, None, 4, 5], 3),
        )

    def test_out_of_range_window_raises(self):
        for window in (0, -1, 1001):
            with self.subTest(window=window):
                with self.assertRaises(ValueError):
                    smooth([0, 1], [1, 2], window)


class PurityTest(unittest.TestCase):
    def setUp(self):
        self.data = dataset([0, 1, 2, 3, 4], [1.0, 2.0, 3.0, 4.0, 5.0])
        self.chain = [{"plugin": "moving-average", "enabled": True, "params": {"window": 3}}]

    def test_input_is_not_modified(self):
        snapshot = copy.deepcopy(self.data)
        apply_chain(self.data, self.chain)
        self.assertEqual(snapshot, self.data)

    def test_original_values_are_recoverable_after_disabling(self):
        filtered = apply_chain(self.data, self.chain)
        restored = apply_chain(self.data, [dict(self.chain[0], enabled=False)])
        self.assertNotEqual(filtered["series"][0]["y"]["data"], restored["series"][0]["y"]["data"])
        self.assertEqual(self.data["series"][0]["y"]["data"], restored["series"][0]["y"]["data"])

    def test_x_and_annotations_are_untouched(self):
        data = json.loads((EXAMPLES / "example-basic.json").read_text(encoding="utf-8"))
        out = apply_chain(data, self.chain)
        self.assertEqual(data["series"][0]["x"], out["series"][0]["x"])
        self.assertEqual(data["annotations"], out["annotations"])

    def test_unknown_fields_survive(self):
        data = json.loads((EXAMPLES / "example-basic.json").read_text(encoding="utf-8"))
        data["series"][0]["extensions"] = {"plugin_private": True}
        out = apply_chain(data, self.chain)
        self.assertEqual({"plugin_private": True}, out["series"][0]["extensions"])
        self.assertEqual(data["meta"]["notes"], out["meta"]["notes"])
        self.assertEqual(data["series"][1]["x"]["extensions"], out["series"][1]["x"]["extensions"])

    def test_filtered_output_still_passes_contract_validation(self):
        data = json.loads((EXAMPLES / "example-basic.json").read_text(encoding="utf-8"))
        out = apply_chain(data, self.chain)
        result = validate(out)
        self.assertTrue(result.ok, result.describe())


class PluginDeclarationTest(unittest.TestCase):
    def test_builtin_plugin_is_registered(self):
        self.assertIn("moving-average", [p.id for p in list_plugins()])

    def test_params_declaration_is_complete(self):
        for decl in get_plugin("moving-average").declare_params():
            with self.subTest(param=decl.get("name")):
                self.assertTrue(decl.get("name"))
                self.assertTrue(decl.get("type"))
                self.assertIn("default", decl)
                self.assertIn("min", decl)
                self.assertIn("max", decl)

    def test_params_declaration_cannot_be_mutated_from_outside(self):
        plugin = get_plugin("moving-average")
        plugin.declare_params()[0]["default"] = 999
        self.assertEqual(5, plugin.declare_params()[0]["default"])

    def test_plugin_declares_need_for_full_data(self):
        self.assertTrue(get_plugin("moving-average").needs_full_data)

    def test_unknown_plugin_error_lists_registered_ids(self):
        with self.assertRaises(ValueError) as ctx:
            get_plugin("no-such-filter")
        self.assertIn("moving-average", str(ctx.exception))


class ChainTest(unittest.TestCase):
    """链的行为：顺序、开关、默认值、缓存键。"""

    @classmethod
    def setUpClass(cls):
        # 顺序只有在"不可交换"的两个插件之间才测得出来，故临时注册一对测试插件
        register(
            FilterPlugin(
                id="t-scale",
                display_name="测试-倍乘",
                version="0.0.0",
                apply=_scale,
                declare_params=lambda: [{"name": "factor", "type": "float", "default": 2}],
            )
        )
        register(
            FilterPlugin(
                id="t-offset",
                display_name="测试-加常数",
                version="0.0.0",
                apply=_offset,
                declare_params=lambda: [{"name": "add", "type": "float", "default": 1}],
            )
        )

    @classmethod
    def tearDownClass(cls):
        # register 没有对称的注销接口，直接清内部表，免得污染同进程的其它用例
        for plugin_id in ("t-scale", "t-offset"):
            chain_module._PLUGINS.pop(plugin_id, None)

    def test_order_matters(self):
        data = dataset([0, 1], [1.0, 2.0])
        scale_then_shift = apply_chain(
            data,
            [
                {"plugin": "t-scale", "params": {"factor": 2}},
                {"plugin": "t-offset", "params": {"add": 1}},
            ],
        )
        shift_then_scale = apply_chain(
            data,
            [
                {"plugin": "t-offset", "params": {"add": 1}},
                {"plugin": "t-scale", "params": {"factor": 2}},
            ],
        )
        self.assertEqual([3.0, 5.0], scale_then_shift["series"][0]["y"]["data"])
        self.assertEqual([4.0, 6.0], shift_then_scale["series"][0]["y"]["data"])

    def test_disabled_step_is_skipped(self):
        data = dataset([0, 1], [1.0, 2.0])
        out = apply_chain(data, [{"plugin": "t-scale", "enabled": False, "params": {"factor": 3}}])
        self.assertEqual([1.0, 2.0], out["series"][0]["y"]["data"])

    def test_empty_chain_returns_input_unchanged(self):
        data = dataset([0, 1], [1.0, 2.0])
        self.assertIs(data, apply_chain(data, None))
        self.assertIs(data, apply_chain(data, []))

    def test_missing_params_fall_back_to_declared_defaults(self):
        data = dataset([0, 1], [10.0, 20.0])
        out = apply_chain(data, [{"plugin": "t-scale"}])
        self.assertEqual([20.0, 40.0], out["series"][0]["y"]["data"])

    def test_unknown_plugin_in_chain_raises(self):
        with self.assertRaises(ValueError):
            apply_chain(dataset([0], [1.0]), [{"plugin": "没这个"}])

    def test_chain_key_tracks_params_order_and_switch(self):
        base = [{"plugin": "moving-average", "enabled": True, "params": {"window": 5}}]
        same = [{"plugin": "moving-average", "enabled": True, "params": {"window": 5}}]
        other_params = [{"plugin": "moving-average", "enabled": True, "params": {"window": 7}}]
        disabled = [{"plugin": "moving-average", "enabled": False, "params": {"window": 5}}]

        self.assertEqual(chain_key(base), chain_key(same))
        self.assertNotEqual(chain_key(base), chain_key(other_params))
        self.assertNotEqual(chain_key(base), chain_key(disabled))
        self.assertNotEqual(
            chain_key([{"plugin": "t-scale"}, {"plugin": "t-offset"}]),
            chain_key([{"plugin": "t-offset"}, {"plugin": "t-scale"}]),
        )


if __name__ == "__main__":
    unittest.main()
