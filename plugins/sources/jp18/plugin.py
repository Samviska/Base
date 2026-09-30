"""JP18 三电极心电日志（十六进制文本）→ 契约数据。

包结构（用真实日志反推，320 个子包包头零失配、样本数正好整数）：

    子包 = 0x88 包头 + 66 组 × 3 字节 + 末尾 4 字节 = 203 字节
    3 字节按**大端有符号 24 位**解释（即"3 个字节合成有符号 32 位整型"，高位符号扩展）
    样本不足 66 组时用 80 80 80 组补齐；末尾 4 字节不解析

横轴默认用**采样序号**：日志里没有采样率，硬凑毫秒会让波形含义失真。
需要毫秒时用 `sample_rate` 参数换算（origin 用 start，不伪造绝对时间）。
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.contract import validate

VERSION = "1.0.0"

PACKET_SIZE = 203
HEADER = 0x88
TAIL_SIZE = 4
FILL = b"\x80\x80\x80"
HEX_TOKEN = re.compile(r"\b([0-9A-Fa-f]{2})\b")

_PARAMS = [
    {"name": "channel_name", "type": "string", "default": "ECG", "display_name": "序列名"},
    {
        "name": "unit",
        "type": "string",
        "default": "1",
        "display_name": "纵轴单位（原始 ADC 值无量纲，写 1）",
    },
    {
        "name": "sample_rate",
        "type": "float",
        "min": 0,
        "max": 100000,
        "default": 0,
        "display_name": "采样率 Hz（0 = 横轴用采样序号）",
    },
]


def declare_params() -> list[dict]:
    return [dict(decl) for decl in _PARAMS]


def extract(path: str, options: dict) -> dict:
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")

    text = file.read_text(encoding="utf-8", errors="replace")
    raw = bytes(int(token, 16) for token in HEX_TOKEN.findall(text))
    if not raw:
        raise ValueError(
            f"{file.name} 里没有十六进制字节：期望形如 “88 02 72 32 …” 的文本内容"
        )

    samples, stats = _parse(raw)
    if not samples:
        raise ValueError(
            f"{file.name} 没有解析出样本：期望每 {PACKET_SIZE} 字节一个子包、首字节 0x88，"
            f"实际首字节是 {raw[0]:#04x}、共 {len(raw)} 字节"
        )

    dataset = _build(file, samples, stats, options)
    result = validate(dataset)
    if not result.ok:
        # 插件必须自校验：不合规的数据宁可在这里失败，也不要流进核心
        raise ValueError(f"插件产出的数据不符合契约：{result.violations[0].describe()}")
    return dataset


def _parse(raw: bytes) -> tuple[list[int], dict]:
    samples: list[int] = []
    packets = 0
    bad_headers = 0
    fill_groups = 0

    for start in range(0, len(raw) - PACKET_SIZE + 1, PACKET_SIZE):
        chunk = raw[start : start + PACKET_SIZE]
        if chunk[0] != HEADER:
            bad_headers += 1
            continue
        packets += 1
        body = chunk[1 : PACKET_SIZE - TAIL_SIZE]
        for offset in range(0, len(body) - 2, 3):
            group = body[offset : offset + 3]
            if group == FILL:
                fill_groups += 1
                continue
            samples.append(int.from_bytes(group, "big", signed=True))

    return samples, {"packets": packets, "bad_headers": bad_headers, "fill_groups": fill_groups}


def _build(path: Path, samples: list[int], stats: dict, options: dict) -> dict:
    name = str(options.get("channel_name") or "ECG")
    unit = str(options.get("unit") or "1")
    rate = float(options.get("sample_rate") or 0)

    if rate > 0:
        x_axis = {
            "kind": "time",
            "unit": "ms",
            "origin": "start",
            "display_name": "时间",
            "tick_format": "offset_seconds",
            "monotonic": True,
            "data": [round(index * 1000.0 / rate, 3) for index in range(len(samples))],
        }
        axis_note = f"按 {rate:g} Hz 把采样序号换算为毫秒（相对起点）"
    else:
        x_axis = {
            "kind": "sequence",
            "unit": "sample",
            "display_name": "采样序号",
            "monotonic": True,
            "data": list(range(len(samples))),
        }
        axis_note = "日志未声明采样率，横轴为采样序号（可用 sample_rate 参数换算为毫秒）"

    notes = [axis_note, "纵轴为原始 ADC 值，未做物理量换算"]
    if stats["fill_groups"]:
        notes.append(f"跳过 {stats['fill_groups']} 组 80 80 80 填充")
    if stats["bad_headers"]:
        notes.append(f"有 {stats['bad_headers']} 个子包首字节不是 0x88，已跳过")

    return {
        "schema_version": "1.0",
        "meta": {
            "source": path.name,
            "extractor": f"jp18@{VERSION}",
            "sample_count": len(samples),
            "notes": "；".join(notes),
        },
        "series": [
            {
                "name": name,
                "unit": unit,
                "x": x_axis,
                "y": {"data": samples},
            }
        ],
    }
