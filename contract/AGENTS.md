# contract/ 就地规则

> 本目录是数据契约的**权威定义**。
> 契约位于依赖图的根：**谁都可以依赖它，它不可以依赖任何人。**
>
> 完整文档：`docs/contract.md`（字段定义）、`docs/modules/contract.md`（模块规则）

1. **改动必须凑齐四件事，缺一不可**：
   升版本号 → 改 `schema/` → 改校验器 → 更新 `docs/contract.md`，
   并在 `docs/DEVLOG.md` 写明**影响面与是否需要迁移**。
2. **未知字段必须原样保留。** `examples/example-basic.json` 里的 `extensions`
   就是用来验证这一点的（读进来再写出去，逐字段比对）。
3. **`examples/` 必须成对**：一份合法、一份对应的非法。
   文件名以 `invalid-` 开头的**必须被拒绝**——用来证明校验器不是在放水。
4. **校验强度分层**：核心属性（如 `scale`）严格校验；
   扩展属性（如未知的 `kind`）允许存在，只做结构校验。
5. schema 只约束结构；**`x` 与 `y` 等长**这类跨字段检查由校验器补充实现。

改完跑一遍：`python scripts/check_docs.py`
