# 怎么加一个滤波插件

> **状态**：可用。接口已落地，见 [modules/filter.md](../modules/filter.md)。

---

## 适用场景

需要一个新的数据处理算法（滑动平均、中值、去趋势、单位换算等）。

## 前置条件

- 已读 [modules/filter.md](../modules/filter.md)
- 明确该算法**是否需要前后文**（有状态算法尤其要注意）

## 步骤

1. 在 `backend/filters/` 下新建一个模块（例如 `median.py`），实现两个函数：

   ```python
   def declare_params() -> list[dict]:
       # 界面据此生成控件；新建参数不得要求改核心或界面代码
       return [{"name": "window", "type": "int", "min": 1, "max": 1000, "default": 5}]

   def apply(data: dict, params: dict) -> dict:
       # 纯函数：返回新对象，不改 data。原地改写会让"关掉滤波"无法恢复原数据
       return {**data, "series": [...]}
   ```

2. 导出一个 `FilterPlugin`：

   ```python
   PLUGIN = FilterPlugin(
       id="median",                 # 小写连字符，与消息里的 "plugin" 字段一致
       display_name="中值滤波",
       version="1.0.0",
       apply=apply,
       declare_params=declare_params,
       needs_full_data=True,        # 需要前后文（中值窗口跨当前点两侧）
   )
   ```

3. 在 `backend/filters/__init__.py` 里 `register(PLUGIN)`。
   内置插件在此显式登记；外部插件放 `plugins/filters/<名字>/`，目录扫描机制待建。

4. 自检：拿 `contract/examples/example-basic.json` 过一遍，输出仍要能通过契约校验器。

## 验证方式

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend/tests -t . -v
```

- 输入数据在调用后**未被修改**（深比较验证）
- 关闭该步骤（`enabled: false`）后数据恢复原样
- 输出仍能通过契约校验器（`backend.contract.validate`）
- 参数可在界面调节，**无需改核心或界面代码**

## 常见错误

| 现象 | 原因 |
| --- | --- |
| 关闭滤波后数据没恢复 | 原地修改了输入数组 |
| 边界数据失真 | 只拿到视口数据，缺前后文——滤波必须拿全量 |
| 拖了滑块图没变 | 参数变化未触发缓存失效（缓存键用 `chain_key`） |
| 界面控件没生成 | `declare_params` 的类型/范围/默认值不完整 |
| 插件的 `extensions` 消失 | `apply` 里重建了 series 或 y，而不是 `{**原对象, ...}` |
