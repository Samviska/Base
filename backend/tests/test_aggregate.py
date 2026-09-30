#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""聚合用例：视口裁剪、像素列 min/max、列边界与缺失值。

最关键的一条是"尖峰必须可见"：本模块存在的理由就是它，
其余用例都是围绕"不丢极值"这个前提展开的。

在仓库根运行：python -m unittest discover -s backend/tests -t . -v
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from backend.aggregate import aggregate_range

EXAMPLES = Path(__file__).resolve().parents[2] / "contract" / "examples"


def series(name: str, xs: list, ys: list, kind: str = "sequence") -> dict:
    return {"name": name, "unit": "1", "x": {"kind": kind, "data": xs}, "y": {"data": ys}}


def dataset(*items: dict) -> dict:
    return {"schema_version": "1.0", "meta": {"source": "t", "extractor": "t@1"}, "series": list(items)}


class RawPointsTest(unittest.TestCase):
    """点数未超过分辨率：返回原始点，且 ymin[i] == ymax[i]。"""

    def test_raw_points_are_returned_unchanged(self):
        data = dataset(series("温度", [0, 1, 2], [25.1, None, 25.4]))
        out = aggregate_range(data, x0=0, x1=2, resolution=10)

        self.assertFalse(out["aggregated"])
        self.assertEqual([0, 1, 2], out["series"][0]["x"])
        self.assertEqual([25.1, None, 25.4], out["series"][0]["ymin"])
        self.assertEqual(out["series"][0]["ymin"], out["series"][0]["ymax"])

    def test_exact_resolution_count_still_returns_raw_points(self):
        data = dataset(series("s", list(range(10)), list(range(10))))
        out = aggregate_range(data, x0=0, x1=9, resolution=10)
        self.assertFalse(out["aggregated"])
        self.assertEqual(10, len(out["series"][0]["x"]))


class ViewportTest(unittest.TestCase):
    def test_points_outside_viewport_are_excluded(self):
        # 视口外放一个更极端的值：它不该出现在结果里
        data = dataset(series("s", [0, 1, 2, 3, 4], [1, -999, 2, 3, 4]))
        out = aggregate_range(data, x0=2, x1=4, resolution=10)
        self.assertEqual([2, 3, 4], out["series"][0]["x"])
        self.assertEqual([2, 3, 4], out["series"][0]["ymax"])

    def test_viewport_boundaries_are_inclusive(self):
        data = dataset(series("s", [0, 1, 2, 3], [10, 20, 30, 40]))
        out = aggregate_range(data, x0=1, x1=2, resolution=10)
        self.assertEqual([1, 2], out["series"][0]["x"])

    def test_points_with_null_x_are_skipped(self):
        data = dataset(series("s", [None, 1, 2], [1, 2, 3]))
        out = aggregate_range(data, x0=0, x1=10, resolution=10)
        self.assertEqual([1, 2], out["series"][0]["x"])

    def test_empty_viewport_is_not_an_error(self):
        data = dataset(series("s", [0, 1, 2], [1, 2, 3]))
        for x0, x1 in ((5, 5), (5, 4)):
            with self.subTest(x0=x0, x1=x1):
                out = aggregate_range(data, x0=x0, x1=x1, resolution=4)
                self.assertFalse(out["aggregated"])
                self.assertEqual([], out["series"][0]["x"])


class PixelColumnTest(unittest.TestCase):
    def test_more_points_than_resolution_returns_min_max_pairs(self):
        data = dataset(series("s", list(range(100)), [float(i) for i in range(100)]))
        out = aggregate_range(data, x0=0, x1=99, resolution=10)

        self.assertTrue(out["aggregated"])
        self.assertEqual(10, len(out["series"][0]["x"]))
        self.assertEqual(10, len(out["series"][0]["ymin"]))
        self.assertEqual(10, len(out["series"][0]["ymax"]))

    def test_single_spike_survives_aggregation(self):
        # 本模块存在的理由：1000 点里藏一个尖峰，全览时必须还能看到它
        ys = [0.0] * 1000
        ys[537] = 999.0
        data = dataset(series("s", list(range(1000)), ys))

        out = aggregate_range(data, x0=0, x1=999, resolution=10)
        self.assertTrue(out["aggregated"])
        self.assertIn(999.0, out["series"][0]["ymax"])

    def test_single_dip_survives_aggregation(self):
        ys = [0.0] * 1000
        ys[123] = -500.0
        data = dataset(series("s", list(range(1000)), ys))

        out = aggregate_range(data, x0=0, x1=999, resolution=10)
        self.assertIn(-500.0, out["series"][0]["ymin"])

    def test_column_boundaries_are_half_open_and_last_column_takes_right_edge(self):
        # x1 = 400、resolution = 4 → 列宽 100；x=100 属第 1 列，x=400 属最后一列
        data = dataset(series("s", [0, 100, 200, 300, 400], [1, 2, 3, 4, 5]))
        out = aggregate_range(data, x0=0, x1=400, resolution=4)

        self.assertTrue(out["aggregated"])
        self.assertEqual([1, 2, 3, 4], out["series"][0]["ymin"])
        self.assertEqual([1, 2, 3, 5], out["series"][0]["ymax"])

    def test_column_centers_are_evenly_spaced(self):
        data = dataset(series("s", list(range(100)), [1.0] * 100))
        out = aggregate_range(data, x0=0, x1=99, resolution=10)
        xs = out["series"][0]["x"]
        self.assertAlmostEqual(xs[0], 99 / 10 / 2)
        gaps = {round(b - a, 9) for a, b in zip(xs, xs[1:])}
        self.assertEqual({round(99 / 10, 9)}, gaps)


class NullTest(unittest.TestCase):
    def test_null_does_not_participate_in_min_max(self):
        xs = list(range(8))
        ys = [None, 5.0, None, 1.0, None, 9.0, None, 3.0]
        data = dataset(series("s", xs, ys))

        out = aggregate_range(data, x0=0, x1=7, resolution=2)
        self.assertEqual([1.0, 3.0], out["series"][0]["ymin"])
        self.assertEqual([5.0, 9.0], out["series"][0]["ymax"])

    def test_all_null_column_keeps_none(self):
        xs = list(range(8))
        ys = [None] * 4 + [1.0, 2.0, 3.0, 4.0]
        data = dataset(series("s", xs, ys))

        out = aggregate_range(data, x0=0, x1=7, resolution=2)
        self.assertIsNone(out["series"][0]["ymin"][0])
        self.assertIsNone(out["series"][0]["ymax"][0])
        self.assertEqual(1.0, out["series"][0]["ymin"][1])


class SelectionTest(unittest.TestCase):
    def test_names_select_a_subset(self):
        data = dataset(series("a", [0, 1], [1, 2]), series("b", [0, 1], [3, 4]))
        out = aggregate_range(data, x0=0, x1=1, resolution=4, names=["b"])
        self.assertEqual(["b"], [s["name"] for s in out["series"]])

    def test_unknown_names_are_ignored(self):
        data = dataset(series("a", [0, 1], [1, 2]))
        out = aggregate_range(data, x0=0, x1=1, resolution=4, names=["不存在"])
        self.assertEqual([], out["series"])

    def test_categorical_axis_is_viewed_by_index(self):
        data = dataset(series("状态", ["待机", "启动", "运行", "停止"], [1, 2, 3, 4], kind="categorical"))
        out = aggregate_range(data, x0=1, x1=2, resolution=4)
        self.assertEqual([1, 2], out["series"][0]["x"])
        self.assertEqual([2, 3], out["series"][0]["ymin"])


class InputContractTest(unittest.TestCase):
    def test_resolution_must_be_positive(self):
        data = dataset(series("s", [0, 1], [1, 2]))
        with self.assertRaises(ValueError):
            aggregate_range(data, x0=0, x1=1, resolution=0)

    def test_length_mismatch_raises_instead_of_truncating(self):
        data = dataset(series("s", [0, 1, 2], [1, 2]))
        with self.assertRaises(ValueError):
            aggregate_range(data, x0=0, x1=2, resolution=4)

    def test_missing_series_raises(self):
        with self.assertRaises(ValueError):
            aggregate_range({"schema_version": "1.0"}, x0=0, x1=1, resolution=4)

    def test_input_is_not_modified(self):
        data = dataset(series("s", list(range(10)), [float(i) for i in range(10)]))
        snapshot = copy.deepcopy(data)
        aggregate_range(data, x0=0, x1=9, resolution=4)
        self.assertEqual(snapshot, data)


class ExampleIntegrationTest(unittest.TestCase):
    """用契约示例跑一遍：示例就是这里最真实的输入。"""

    def setUp(self):
        self.data = json.loads((EXAMPLES / "example-basic.json").read_text(encoding="utf-8"))

    def test_temperature_series_aggregates_and_skips_null(self):
        out = aggregate_range(self.data, x0=0, x1=400, resolution=2, names=["温度"])
        result = out["series"][0]
        self.assertTrue(out["aggregated"])
        self.assertEqual([25.1, 26.0], result["ymin"])
        self.assertEqual([25.3, 26.2], result["ymax"])

    def test_categorical_series_returns_raw_points(self):
        out = aggregate_range(self.data, x0=0, x1=3, resolution=10, names=["状态计数"])
        self.assertFalse(out["aggregated"])
        self.assertEqual([0, 1, 2, 3], out["series"][0]["x"])
        self.assertEqual([1, 2, 3, 4], out["series"][0]["ymax"])

    def test_all_series_when_names_omitted(self):
        out = aggregate_range(self.data, x0=0, x1=400, resolution=100)
        self.assertEqual(["温度", "状态计数"], [s["name"] for s in out["series"]])


if __name__ == "__main__":
    unittest.main()
