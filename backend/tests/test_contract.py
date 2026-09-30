#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""契约校验器的用例。

示例部分直接遍历 contract/examples/ 而不是逐个写死文件名：
新增示例自动纳入，避免"加了示例却没人校验"。

在仓库根运行：python -m unittest discover -s backend/tests -t . -v
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from backend.contract import CROSS_FIELD, JSON_ERROR, validate, validate_file

EXAMPLES = Path(__file__).resolve().parents[2] / "contract" / "examples"


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


class ExampleTest(unittest.TestCase):
    """示例与校验器必须一致：合法示例通过，invalid- 示例被拒绝且能定位。"""

    def test_examples_match_expectation(self):
        for path in sorted(EXAMPLES.glob("*.json")):
            with self.subTest(example=path.name):
                result = validate(json.loads(path.read_text(encoding="utf-8")))
                if path.name.startswith("invalid-"):
                    self.assertFalse(result.ok, "非法示例被接受，说明校验器在放水")
                    self.assertTrue(
                        any(v.path for v in result.violations),
                        "被拒绝但未指出出错字段路径",
                    )
                else:
                    self.assertTrue(result.ok, f"合法示例被拒绝：{result.describe()}")

    def test_missing_unit_points_at_series(self):
        paths = [v.path for v in validate(load("invalid-missing-unit.json")).violations]
        self.assertIn("series[0]", paths)

    def test_time_without_origin_points_at_x(self):
        paths = [v.path for v in validate(load("invalid-time-no-origin.json")).violations]
        self.assertIn("series[0].x", paths)

    def test_unknown_kind_without_numeric_values_points_at_x(self):
        paths = [v.path for v in validate(load("invalid-unknown-kind.json")).violations]
        self.assertIn("series[0].x", paths)

    def test_unknown_kind_with_numeric_values_is_accepted(self):
        # S6 的结构前提：未知 kind 本身合法，只是必须声明 numeric_values
        self.assertTrue(validate(load("example-unknown-kind.json")).ok)

    def test_length_mismatch_is_caught_by_cross_field_rule(self):
        result = validate(load("invalid-length-mismatch.json"))
        violation = next(v for v in result.violations if v.keyword == CROSS_FIELD)
        self.assertEqual("series[0].y.data", violation.path)

    def test_unknown_fields_survive_round_trip(self):
        # 硬规则：往返不得丢弃契约不认识的字段，插件的 extensions 靠它存活
        basic = load("example-basic.json")
        self.assertIn("category_order", basic["series"][1]["x"]["extensions"])
        self.assertEqual(basic, json.loads(json.dumps(basic)))


class ValidateTest(unittest.TestCase):
    def test_top_level_problem_uses_empty_path(self):
        result = validate({})
        self.assertFalse(result.ok)
        self.assertIn("", [v.path for v in result.violations])
        self.assertTrue(result.error_detail()["reason"])

    def test_non_object_input_is_rejected_not_crashing(self):
        for data in ([], "文本", 3, None):
            with self.subTest(data=data):
                self.assertFalse(validate(data).ok)

    def test_input_is_not_modified(self):
        basic = load("example-basic.json")
        snapshot = copy.deepcopy(basic)
        validate(basic)
        self.assertEqual(snapshot, basic)

    def test_validate_file_reads_example(self):
        self.assertTrue(validate_file(EXAMPLES / "example-basic.json").ok)

    def test_validate_file_reports_broken_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{ 不是 JSON", encoding="utf-8")
            result = validate_file(bad)
        self.assertFalse(result.ok)
        self.assertEqual(JSON_ERROR, result.violations[0].keyword)

    def test_validate_file_reports_missing_file(self):
        result = validate_file(EXAMPLES / "不存在的示例.json")
        self.assertFalse(result.ok)
        self.assertEqual(JSON_ERROR, result.violations[0].keyword)


if __name__ == "__main__":
    unittest.main()
