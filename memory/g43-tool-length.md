---
name: g43-tool-length
description: G43/G49 工具长度运行时配置 — 第二版本待实现
metadata: 
  node_type: memory
  type: project
  originSessionId: 035d3572-d50d-4036-8034-7338cb07b49b
---

# G43 工具长度运行时配置

## 需求

运行时动态修改 `tool_length`，支持换笔场景（不同长度画笔切换，或画笔磨损补偿）。

## 功能

- `G43 L<length>` — 设置新的 tool_length（单位 mm），RTCP 补偿立即生效
- `G43` (无参数) — 报告当前 tool_length
- `G49` — 取消工具长度补偿（设 tool_length=0，等同于无 RTCP）

## 实现要点

- 在 `cartesian_rtcp.py` 中增加 `set_tool_length()` 方法
- 注册 G-code 命令 `G43` 和 `G49`
- 修改后 `_apply_rtcp` / `_apply_inverse_rtcp` 使用新的 L 值
- 换刀时注意坐标空间一致性（TIP vs PIVOT）

## 优先级

第二版本，当前先做速度模型改进。

## 记录日期

2026-05-23
