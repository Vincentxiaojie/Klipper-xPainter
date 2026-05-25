---
name: gcode-macro-override
description: gcode_macro 覆盖内置命令（M18）时 gcode.py 需允许 re-registration
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 14188333-1cad-4855-8b24-379d0a07c965
---

gcode.py `register_command` 上游原版对重复注册会抛 config_error，但 stepper_enable 自动加载时已注册 M18，导致 `[gcode_macro M18]` 在真机配置中崩溃。

**Why:** stepper.py:291 在处理任何 stepper 段时自动加载 stepper_enable，后者无条件注册 M18/M84。后续 `[gcode_macro M18]` 再注册同一命令时触发 gcode.py:142 的严格检查。

**How to apply:** `gcode.py` 中 `register_command` 对已存在的命令应用 debug log + 覆盖旧 handler，而非抛 error。Klipper 标准测试套件未覆盖此场景（无任何测试定义 `[gcode_macro M18]`），已在 `test/klippy/macro_override.test` 添加专门回归测试。
