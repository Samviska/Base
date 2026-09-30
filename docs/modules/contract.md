# 模块：契约（Contract）

## 1. 一句话职责

定义数据长什么样，并提供校验。

**不负责**：数据的产生、处理、存储、绘制。

## 2. 代码位置

| 内容 | 路径 |
| --- | --- |
| 语言中立的权威定义 | `contract/schema/dataset.schema.json` |
| 示例数据（供测试与自检） | `contract/examples/` |
| 校验用例（语言中立，当前为空） | `contract/tests/` |
| 校验器实现 | `backend/contract/validator.py` |
| 校验器对外入口 | `backend/contract/__init__.py` |
| Python 侧用例 | `backend/tests/test_contract.py` |

## 3. 对外接口

```python
from backend.contract import validate, validate_file

result = validate(data)      # 任意 Python 对象（通常是 json.load 的结果）；不修改入参
result.ok                    # bool
result.violations            # tuple[Violation]，每条含 path / reason / keyword
result.error_detail()        # {"path": ..., "reason": ...}，直接用 M 消息 CONTRACT_VIOLATION 的 detail
result.describe()            # ["series[0].unit: 缺少必填字段（...）"]，供日志与插件自检
validate_file(path)          # 读 UTF-8 JSON 再校验；读不到或语法错也作为违规返回
```

| 项 | 约定 |
| --- | --- |
| **路径格式** | `series[0].unit`；**空串表示问题出在整份文档上**（如顶层缺 `schema_version`） |
| **`keyword`** | 触发规则。schema 关键字之外还有两个：`contract`（跨字段规则）、`json`（读取或语法错误） |
| **校验顺序** | 先 schema，**通过后才查跨字段**；故 `violations` 里要么是结构错误、要么是跨字段错误 |
| **跨字段范围** | 目前只有一条：`series[i].x.data` 与 `series[i].y.data` 必须等长 |
| **自身故障** | schema 文件缺失或不是合法 JSON 时抛 `RuntimeError`——校验器坏了不能伪装成"数据违规" |
| **自动化调用点** | `scripts/check_docs.py`（pre-commit 与 CI）、`backend/tests/test_contract.py` |

字段定义见 [../contract.md](../contract.md)，本文档不重复。

## 4. 依赖规则

| | |
| --- | --- |
| 可以依赖 | 无 |
| **禁止依赖** | 任何业务模块 |

契约**不依赖任何模块**，所有模块依赖它。这是整个依赖图的根。

## 5. 扩展点

扩展区（`extensions`）允许插件携带自定义信息，核心**只透传不解释**。

新增字段前先判断它属于哪一层：

| 层 | 判断依据 |
| --- | --- |
| 最小语义集 | 渲染器**必须**理解才能正确绘制 |
| 描述信息 | 渲染器可以忽略，不影响正确性 |
| 扩展区 | 只有专用插件才认识 |

## 6. 本模块的硬规则

1. **契约不依赖任何模块。**
2. **未知字段必须原样保留**：读进来再写出去，逐字段比对不得有丢失。
   - 否则插件的 `extensions` 会静默消失，扩展区形同虚设。
3. **校验强度分层**：核心属性严格校验（可拒绝非法值），扩展属性只做结构校验。
   - 例：`scale` 必须是已知值；`kind` 允许未知。
4. **变更时必须同时更新**：`docs/contract.md`、校验器、受影响的模块文档、`DEVLOG.md`。
5. **校验器不新增约束**：它只把 `contract/` 里已定义的东西变成可执行的检查。
   收紧规则（例如要求序列名唯一）属于契约变更，走 [../guides/contract-change.md](../guides/contract-change.md)。

## 7. 已知的坑

| 坑 | 现象 | 应对 |
| --- | --- | --- |
| 文档与校验器不同步 | 文档说合法，校验器却拒绝 | 同一提交内改完，并用"往返测试"兜底 |
| 序列化丢字段 | 插件的 `extensions` 消失 | 加"读进来再写出去、逐字段比对"的测试 |
| 单位为空 | 界面显示空白 | 校验器强制 `unit` 非空，无量纲写 `"1"` |
| 校验错误信息不定位 | 报"数据不合法"，但不知哪儿错 | 校验结果必须带**字段路径** |
| schema 未过时又查跨字段 | 一条错误派生出一串无关报错，真问题被淹没 | 先 schema，通过后才查跨字段 |
| schema 文件读不到 | 若伪装成数据违规，人会去改本来正确的数据 | 抛 `RuntimeError`，报错直接指向契约文件 |
| 顶层字段缺失时路径为空串 | 误判成"没有字段路径" | 空串即整份文档（JSON Pointer 的根） |

## 8. 相关

- 字段定义：[../contract.md](../contract.md)
- 决策背景：[../DECISIONS.md](../DECISIONS.md) D8
- 变更流程：[../contract.md](../contract.md) §9
