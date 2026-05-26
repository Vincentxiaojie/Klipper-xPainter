---
name: test-coverage-gap
description: 真机配置场景的测试盲区：gcode_macro 覆盖 stepper_enable 内置命令
metadata: 
  node_type: memory
  type: project
  originSessionId: 14188333-1cad-4855-8b24-379d0a07c965
---

真机测试因 `gcode command M18 already registered` 崩溃，但 53 个标准 Klipper 测试全部通过。根本原因是标准测试套件中无任何用例定义 `[gcode_macro M18]`，无法覆盖 stepper_enable 自动注册 M18 后再被 gcode_macro 覆盖的场景。

**Why:** 真机 `printer.cfg` 需要自定义 M18 来管理 5 轴（X/Y/Z/B/C）电机，但标准测试只用 `commands.test` 发送裸 M18 测试内置 handler。

**How to apply:** 新增 `test/klippy/macro_override.test` 专门覆盖此场景。未来对 `gcode.py` 或 `stepper_enable.py` 的任何修改都应运行此测试确保不回归。
