# 怎么加一个渲染器

> **状态**：待建。前置：先读 [modules/renderer.md](../modules/renderer.md)。

---

## 适用场景

内置图形不满足需求，需要一个新的视觉形态（散点、面积、热力图、专用波形图等）。

## 前置条件

- 已读 [modules/renderer.md](../modules/renderer.md)（尤其"硬规则"与"已知的坑"）
- 已了解数据结构：[contract.md](../contract.md)

## 步骤（待补全）

1. 复制模板目录（**待建**：`plugins/renderers/_template/`）
2. 实现接口：`mount` / `unmount` / `setData` / `appendData` / `setViewport` / `setAnnotations` / `on`
3. 写 manifest（名称、类型、版本、入口、文案）
4. 自检

## 验证方式（待补全）

- 核心代码**零改动**
- 删掉内置实现后核心不报错，只是少一个选项
- 缩放、平移、标记全部可用
- 大数据下尖峰仍可见

## 常见错误

| 现象 | 原因 |
| --- | --- |
| 数据变了图没变 | 没有显式重绘 |
| 缩放后 tooltip 位置错 | 坐标换算写在多处 |
| 点一多就卡 | 用了 SVG 而不是 Canvas |
