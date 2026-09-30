# 怎么加一个数据源插件

> **状态**：可用。接口已落地，见 [modules/source.md](../modules/source.md)；
> 完整实例参考 `plugins/sources/jp18/`（十六进制心电日志）。

---

## 适用场景

出现一种新的日志格式需要解析；或将来要做实时数据流（持续模式）。

## 前置条件

- 已读 [modules/source.md](../modules/source.md)
- 已读 [contract.md](../contract.md)（输出必须符合契约）
- 手头有**真实日志样本**（不要凭想象写解析）

## 步骤

1. 新建 `plugins/sources/<名字>/`，放一份 `manifest.json`：

   ```json
   {
     "id": "my-log",
     "type": "source",
     "mode": "oneshot",
     "version": "1.0.0",
     "display_name": "我的日志格式",
     "entry": "plugin.py",
     "notes": "一句话说明它认什么格式"
   }
   ```

2. 同目录放 `plugin.py`，实现两个函数：

   ```python
   from backend.contract import validate

   def declare_params() -> list[dict]:
       # 界面据此自动生成控件；新增参数不得要求改核心或界面代码
       return [{"name": "unit", "type": "string", "default": "1", "display_name": "纵轴单位"}]

   def extract(path: str, options: dict) -> dict:
       samples = ...                      # 解析日志
       dataset = {
           "schema_version": "1.0",
           "meta": {"source": path, "extractor": "my-log@1.0.0", "sample_count": len(samples)},
           "series": [{
               "name": "信号", "unit": options.get("unit") or "1",
               "x": {"kind": "sequence", "unit": "sample", "data": list(range(len(samples)))},
               "y": {"data": samples},
           }],
       }
       result = validate(dataset)         # 必须自校验
       if not result.ok:
           raise ValueError(f"产出不符合契约：{result.violations[0].describe()}")
       return dataset
   ```

3. 声明 x 轴描述：有真实时间就用 `kind: "time"` + `origin: "start"` + 毫秒；
   **拿不准就用 `kind: "sequence"`**，不要硬凑单位与基准（[contract.md](../contract.md) §6）。
   缺失值一律 `null`，不得跳过异常点。

4. 重启服务：插件在启动时扫描注册，界面上的插件列表里就会多一项。

## 验证方式

```powershell
.venv\Scripts\python.exe -m unittest backend.tests.test_sources -v
.venv\Scripts\python.exe -m backend.server        # 启动后再跑一次真实的 open_file
```

- 输出的数据能通过校验器，**零违规**
- 同一输入跑两次，结果**完全一致**
- 在界面上选中该插件即可出图，**核心代码零改动**
- 坏插件只影响它自己：故意让入口抛异常，服务仍能启动，界面能看到警告（S4）

## 常见错误

| 现象 | 原因 |
| --- | --- |
| 波形被压缩或拉伸 | 时间精度搞错（微秒当毫秒） |
| x 轴乱序、缩放行为异常 | 日志有乱序行，未排序也未记录 |
| 曲线出现假的 0 值 | 缺失值用了 `0` 而不是 `null` |
| 尖峰消失 | 解析时跳过了异常点 |
| 样本数不是整数、波形出现满量程跳变 | 包切分错位或没跳过填充字节 |
| 插件放进目录却没出现 | `manifest.json` 缺字段或入口文件不在；看服务端日志的警告 |
