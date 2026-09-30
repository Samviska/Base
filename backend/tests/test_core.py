#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核心用例：三层缓存的失效方向、命令分发、错误到错误码的映射。

缓存那几条是本模块的命门——失效漏一层，界面就会给出过期的图，
而且看起来"只是没刷新"，很难查。

在仓库根运行：python -m unittest discover -s backend/tests -t . -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

from backend.core import CoreError, Session, handle

EXAMPLES = Path(__file__).resolve().parents[2] / "contract" / "examples"
BASIC = str(EXAMPLES / "example-basic.json")
UNKNOWN_KIND = str(EXAMPLES / "example-unknown-kind.json")
INVALID_UNIT = str(EXAMPLES / "invalid-missing-unit.json")

SMOOTH = [{"plugin": "moving-average", "enabled": True, "params": {"window": 3}}]


def send(session: Session, msg_type: str, payload: dict | None = None, msg_id: int = 1) -> dict:
    return handle(session, {"id": msg_id, "type": msg_type, "payload": payload or {}})


def opened(path: str = BASIC) -> Session:
    session = Session()
    response = send(session, "open_file", {"path": path})
    assert response["ok"], response
    return session


class CacheTest(unittest.TestCase):
    def test_filtered_result_is_cached_until_chain_changes(self):
        session = opened()
        first = session.filtered()
        self.assertIs(first, session.filtered())

        session.set_chain(SMOOTH)
        self.assertIsNot(first, session.filtered())
        self.assertIs(session.filtered(), session.filtered())

    def test_query_result_is_cached_per_viewport(self):
        session = opened()
        first = session.query(series=None, x0=0, x1=400, resolution=2)
        self.assertIs(first, session.query(series=None, x0=0, x1=400, resolution=2))
        self.assertIsNot(first, session.query(series=None, x0=0, x1=400, resolution=4))

    def test_open_invalidates_aggregate_cache(self):
        session = opened()
        first = session.query(series=["温度"], x0=0, x1=400, resolution=2)
        self.assertEqual([25.1, 26.0], first["series"][0]["ymin"])

        session.open({"schema_version": "1.0", "meta": {}, "series": []}, {"path": "另一份"})
        after = session.query(series=["温度"], x0=0, x1=400, resolution=2)
        self.assertEqual([], after["series"])

    def test_chain_survives_reopening_a_file(self):
        session = opened()
        session.set_chain(SMOOTH)
        session.open({"schema_version": "1.0", "meta": {}, "series": []}, {"path": "另一份"})
        self.assertEqual(SMOOTH, session.chain)

    def test_close_clears_dataset(self):
        session = opened()
        session.close()
        with self.assertRaises(CoreError) as ctx:
            session.filtered()
        self.assertEqual("INVALID_REQUEST", ctx.exception.code)

    def test_filter_is_applied_before_aggregation(self):
        """顺序错了结果直接是错的：这里同时验证顺序与两层缓存失效。"""
        session = opened()
        x0, x1, res = 0, 400, 2

        before = session.query(series=["温度"], x0=x0, x1=x1, resolution=res)
        self.assertEqual([25.1, 26.0], before["series"][0]["ymin"])
        self.assertEqual([25.3, 26.2], before["series"][0]["ymax"])

        session.set_chain(SMOOTH)
        after = session.query(series=["温度"], x0=x0, x1=x1, resolution=res)
        # 滑动平均的结果带浮点残差（25.200000000000003），不比精确值
        self.assertAlmostEqual(25.2, after["series"][0]["ymin"][0])
        self.assertAlmostEqual(26.1, after["series"][0]["ymin"][1])
        self.assertEqual(after["series"][0]["ymin"], after["series"][0]["ymax"])


class OpenFileTest(unittest.TestCase):
    def test_summary_has_shape_without_data(self):
        session = Session()
        response = send(session, "open_file", {"path": BASIC})
        payload = response["payload"]

        self.assertTrue(response["ok"])
        self.assertEqual("sensor_demo.log", payload["meta"]["source"])
        names = [s["name"] for s in payload["series"]]
        self.assertEqual(["温度", "状态计数"], names)

        temperature = payload["series"][0]
        self.assertEqual(5, temperature["point_count"])
        self.assertEqual([0, 400], temperature["x_range"])
        self.assertNotIn("data", temperature["axis"])
        self.assertEqual("time", temperature["axis"]["kind"])

    def test_categorical_axis_range_is_by_index(self):
        session = Session()
        payload = send(session, "open_file", {"path": BASIC})["payload"]
        categorical = payload["series"][1]
        self.assertEqual([0, 3], categorical["x_range"])

    def test_missing_path_is_invalid_request(self):
        response = send(Session(), "open_file", {})
        self.assertEqual("INVALID_REQUEST", response["error"]["code"])

    def test_missing_file_is_file_not_found(self):
        response = send(Session(), "open_file", {"path": str(EXAMPLES / "没有这个.json")})
        self.assertEqual("FILE_NOT_FOUND", response["error"]["code"])

    def test_contract_violation_carries_field_path(self):
        response = send(Session(), "open_file", {"path": INVALID_UNIT})
        self.assertFalse(response["ok"])
        self.assertEqual("CONTRACT_VIOLATION", response["error"]["code"])
        self.assertEqual("series[0]", response["error"]["detail"]["path"])

    def test_unknown_source_plugin_is_reported(self):
        response = send(Session(), "open_file", {"path": BASIC, "source_plugin": "demo-log"})
        self.assertEqual("PLUGIN_NOT_FOUND", response["error"]["code"])
        self.assertIn("contract-json", response["error"]["message"])

    def test_options_must_be_an_object(self):
        response = send(Session(), "open_file", {"path": BASIC, "options": []})
        self.assertEqual("INVALID_REQUEST", response["error"]["code"])


class QueryRangeTest(unittest.TestCase):
    def test_payload_matches_m6(self):
        session = opened()
        response = send(session, "query_range", {"x0": 0, "x1": 400, "resolution": 2})
        payload = response["payload"]

        self.assertTrue(payload["aggregated"])
        self.assertEqual(["温度", "状态计数"], [s["name"] for s in payload["series"]])
        for series in payload["series"]:
            self.assertEqual(len(series["x"]), len(series["ymin"]))
            self.assertEqual(len(series["x"]), len(series["ymax"]))

    def test_subset_of_series(self):
        session = opened()
        payload = send(session, "query_range", {"series": ["温度"], "x0": 0, "x1": 400, "resolution": 2})["payload"]
        self.assertEqual(["温度"], [s["name"] for s in payload["series"]])

    def test_query_before_open_is_invalid_request(self):
        response = send(Session(), "query_range", {"x0": 0, "x1": 1, "resolution": 10})
        self.assertEqual("INVALID_REQUEST", response["error"]["code"])

    def test_bad_arguments_are_rejected(self):
        session = opened()
        cases = [
            {"x0": 0, "x1": 1, "resolution": 0},
            {"x0": 0, "x1": 1, "resolution": 1.5},
            {"x0": "0", "x1": 1, "resolution": 10},
            {"x0": 0, "x1": 1, "resolution": 10, "series": "温度"},
            {"x0": 0, "x1": 1, "resolution": 10, "series": [1]},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual("INVALID_REQUEST", send(session, "query_range", payload)["error"]["code"])

    def test_unexpected_exception_still_gets_a_response(self):
        """兜底分支：畸形数据绕过校验进来时，也要回 INTERNAL 而不是静默。"""
        session = Session()
        session.dataset = {"meta": {}, "series": "不是数组"}
        response = send(session, "query_range", {"x0": 0, "x1": 1, "resolution": 10})
        self.assertFalse(response["ok"])
        self.assertEqual("INTERNAL", response["error"]["code"])


class BrowseTest(unittest.TestCase):
    """列目录：界面选文件靠它，因为浏览器给不出本机路径。"""

    def test_lists_a_directory_with_entries(self):
        payload = send(Session(), "browse", {"path": str(EXAMPLES.parent)})["payload"]
        names = [entry["name"] for entry in payload["entries"]]
        self.assertIn("examples", names)
        self.assertEqual(str(EXAMPLES.parent), payload["path"])
        self.assertTrue(payload["parent"])

    def test_directories_come_first(self):
        payload = send(Session(), "browse", {"path": str(EXAMPLES.parent)})["payload"]
        types = [entry["type"] for entry in payload["entries"]]
        self.assertEqual(sorted(types, key=lambda kind: kind != "dir"), types)

    def test_file_path_falls_back_to_its_directory(self):
        payload = send(Session(), "browse", {"path": str(EXAMPLES / "example-basic.json")})["payload"]
        self.assertEqual(str(EXAMPLES), payload["path"])

    def test_defaults_to_home_directory(self):
        self.assertTrue(send(Session(), "browse")["payload"]["path"])

    def test_files_carry_their_size(self):
        payload = send(Session(), "browse", {"path": str(EXAMPLES)})["payload"]
        files = [entry for entry in payload["entries"] if entry["type"] == "file"]
        self.assertTrue(files)
        self.assertTrue(all(isinstance(entry["size"], int) for entry in files))

    def test_bad_path_type_is_invalid_request(self):
        self.assertEqual("INVALID_REQUEST", send(Session(), "browse", {"path": 123})["error"]["code"])


class PluginAndChainTest(unittest.TestCase):
    def test_list_plugins_reports_both_kinds(self):
        payload = send(Session(), "list_plugins")["payload"]
        by_id = {item["id"]: item for item in payload["plugins"]}

        self.assertEqual("filter", by_id["moving-average"]["type"])
        self.assertEqual("滑动平均", by_id["moving-average"]["display_name"])
        self.assertEqual("window", by_id["moving-average"]["params"][0]["name"])

        self.assertEqual("source", by_id["contract-json"]["type"])
        self.assertEqual("oneshot", by_id["contract-json"]["mode"])
        # 坏插件要能在界面上说出来（S4）
        self.assertIn("warnings", payload)

    def test_set_then_get_filter_chain(self):
        session = opened()
        self.assertEqual({"chain": []}, send(session, "get_filter_chain")["payload"])
        self.assertEqual({"applied": True}, send(session, "set_filter_chain", {"chain": SMOOTH})["payload"])
        self.assertEqual({"chain": SMOOTH}, send(session, "get_filter_chain")["payload"])

    def test_unknown_plugin_in_chain(self):
        response = send(opened(), "set_filter_chain", {"chain": [{"plugin": "没这个"}]})
        self.assertEqual("PLUGIN_NOT_FOUND", response["error"]["code"])

    def test_bad_chain_shape(self):
        session = opened()
        for chain in ("不是数组", [{"无plugin": 1}], [{"plugin": "moving-average", "params": []}]):
            with self.subTest(chain=chain):
                response = send(session, "set_filter_chain", {"chain": chain})
                self.assertEqual("INVALID_REQUEST", response["error"]["code"])

    def test_close_source(self):
        self.assertEqual({"closed": True}, send(opened(), "close_source")["payload"])

    def test_list_storage_formats_is_empty_until_storage_exists(self):
        self.assertEqual({"formats": []}, send(Session(), "list_storage_formats")["payload"])


class EnvelopeTest(unittest.TestCase):
    def test_unknown_type(self):
        response = send(Session(), "made_up_type")
        self.assertFalse(response["ok"])
        self.assertEqual("UNKNOWN_TYPE", response["error"]["code"])
        self.assertEqual("made_up_type", response["type"])

    def test_registered_but_unimplemented_message_says_so(self):
        response = send(opened(), "add_annotation", {"series": "温度", "kind": "point"})
        self.assertEqual("INTERNAL", response["error"]["code"])
        self.assertIn("尚未实现", response["error"]["message"])

    def test_response_echoes_id_and_type(self):
        response = send(Session(), "list_plugins", msg_id=42)
        self.assertEqual(42, response["id"])
        self.assertEqual("list_plugins", response["type"])
        self.assertTrue(response["ok"])

    def test_events_and_broken_envelopes_have_no_response(self):
        self.assertIsNone(handle(Session(), {"type": "query_range", "payload": {}}))
        self.assertIsNone(handle(Session(), "不是对象"))
        self.assertIsNone(handle(Session(), {"id": 1, "type": 123}))

    def test_payload_must_be_an_object(self):
        response = handle(Session(), {"id": 1, "type": "list_plugins", "payload": []})
        self.assertEqual("INVALID_REQUEST", response["error"]["code"])


if __name__ == "__main__":
    unittest.main()
