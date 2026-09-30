# 模块：滤波（Filter）

## 1. 一句话职责

对**全量数据**做处理，输出仍然是全量数据。

**不负责**：读原始日志（那是[数据源](source.md)）、降维（那是[聚合](aggregate.md)）、绘制。

## 2. 代码位置

| 内容 | 路径 |
| --- | --- |
| 处理链与插件登记 | `backend/filters/chain.py` |
| 对外入口 | `backend/filters/__init__.py` |
| 内置示例插件（滑动平均） | `backend/filters/moving_average.py` |
| 用例 | `backend/tests/test_filters.py` |
| 使用者 / 第三方插件 | `plugins/filters/`（"目录即插件"的扫描机制待建） |

## 3. 对外接口

```python
from backend.filters import apply_chain, chain_key, get_plugin, list_plugins

apply_chain(data, chain) -> dict      # 按链顺序处理全量数据；纯函数
chain_key(chain) -> str               # 滤波缓存的键：顺序、开关、参数
list_plugins() -> list[FilterPlugin]  # M 消息 list_plugins 的 filter 部分据此生成
```

链的每一项与 M 消息 `set_filter_chain` 的步骤**是同一个形状**：

```json
{ "plugin": "moving-average", "enabled": true, "params": { "window": 5 } }
```

插件对外只有这些成员：

| 成员 | 作用 |
| --- | --- |
| `id` / `display_name` / `version` | 登记与界面显示 |
| `apply(data, params) -> data` | 对全量数据做处理；**纯函数** |
| `declare_params() -> list[dict]` | 参数声明，界面据此生成控件：每项含 `name`/`type`/`default`，数值型还要 `min`/`max` |
| `needs_full_data` | 算法是否需要前后文（有状态算法恒为真） |

行为约定：

| 项 | 约定 |
| --- | --- |
| 全部步骤都未启用 | **原样返回入参**（同一对象），核心据此可判断"结果未变" |
| 参数缺省 | 按 `declare_params()` 的 `default` 补齐；声明外的参数原样传给插件 |
| 链的顺序 | **有意义**，缓存键因此不排序链本身（只排序每一步内部的对象键） |
| 未知插件 id | 抛 `ValueError` 并列出已注册的 id |
| 插件抛异常 | 本模块**不捕获**：由核心按"插件异常不得让应用崩溃"统一处置（[ARCHITECTURE.md](../ARCHITECTURE.md) §6.3） |

## 4. 依赖规则

| | |
| --- | --- |
| 可以依赖 | 契约 |
| **禁止依赖** | 界面、其他插件、核心内部实现 |

## 5. 扩展点

新增一个滤波算法 = 在 `plugins/filters/<名字>/` 放一个实现文件 + 一份 manifest。
见 [guides/add-filter-plugin.md](../guides/add-filter-plugin.md)。

## 6. 本模块的硬规则

1. **纯函数**：不得修改输入数据，可脱离界面单独测试。
   - 反例：原地改写数组 → 关掉滤波后数据无法恢复。
2. **作用于全量数据**：不是为显示服务的降维，那是聚合的职责。
3. **参数必须自带声明**：新增一个参数**不得要求改动核心代码或界面代码**。
4. **必须声明算法对数据完整性的要求**（是否需要前后文）。见第 7 节第一条坑。

## 7. 已知的坑

| 坑 | 现象 | 应对 |
| --- | --- | --- |
| 有状态的滤波需要邻近点 | 只给视口内的数据会算错（滑动平均边界失真） | **滤波必须拿全量数据**。这正是它被放在后端、且在聚合之前的原因 |
| 原地修改输入 | 关闭滤波后数据没恢复 | 返回新对象 |
| 参数变化未触发重算 | 拖了滑块图没变 | 参数变化必须使滤波缓存与聚合缓存失效 |
| 参数类型声明不全 | 界面控件生成失败 | `declare_params` 里类型、范围、默认值必须完整 |
| 窗口内有缺失值 | 拿邻近点凑平均，凭空造出数据 | 窗口内只要有 `null`，结果就是 `null`（滑动平均就是这么定的） |
| 偶数窗口的居中歧义 | 同一份数据不同实现结果不同 | 明确"窗口为偶数时向左偏一"，并写用例固定下来 |
| 大窗口下逐窗口求和 | 100 万点、窗口 101 要 5 秒，拖一次滑块卡一次 | 用前缀和，耗时与窗口大小无关；缺失值靠"窗口内最后一个 `null` 的位置"判定 |

## 8. 相关

- 数据结构：[contract.md](../contract.md)
- 怎么加插件：[guides/add-filter-plugin.md](../guides/add-filter-plugin.md)
- 为什么必须在后端：[ARCHITECTURE.md](../ARCHITECTURE.md) §2.4
