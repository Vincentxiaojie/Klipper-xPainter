# 五轴 RTCP 油画 CNC 系统 — 项目变更总结

---

## 1. 项目概述

本项目基于 **Klipper** 开源 3D 打印机固件，扩展了以下能力:

- **多轴支持**: 从原来的 3 轴 (XYZ) + 挤出机扩展到最多 **7 轴** (X, Y, Z, E, A, B, C)
- **RTCP (Rotation Tool Center Point)**: 旋转轴倾斜时自动补偿 XYZ 位置，保持笔尖在编程位置不变
- **BC 旋转结构**: B 轴绕 Y 俯仰 (笔的倾斜角度) + C 轴绕 Z 旋转 (长方形笔头的方向控制)
- **油画 CNC 专用**: 为画笔绘画场景优化的运动控制

### 代码规模

| 类别 | 行数 |
|------|------|
| 新增文件 | ~2,500 行 |
| 修改文件 | ~3,300 行 |
| **合计** | **~5,800 行** |

---

## 2. 新增功能

### 2.1 核心功能

| 功能 | 说明 |
|------|------|
| **多轴笛卡尔运动学** | `cartesian_abc.py` — 支持 XYZ + ABC 中任意轴组合，含 E 轴映射 |
| **RTCP 运动学** | `cartesian_rtcp.py` — 笔尖坐标空间与旋转中心空间自动转换 |
| **BC/AB 双旋转配置** | `rotary_config: bc` (B绕Y+C绕Z) 或 `ab` (A绕X+B绕Y) |
| **速度模型改进** | 旋转轴弧长贡献纳入速度预算，笔尖线速度准确匹配 F 值 |
| **旋转轴归零** | G28 完整支持 ABC 旋转轴物理 endstop 归零 |
| **多轴 G92** | 所有轴 (含 ABC) 的动态坐标系偏移 |
| **多轴 GET_POSITION** | M114 和 GET_POSITION API 返回所有轴位置 |

### 2.2 C 层扩展

| 功能 | 文件 |
|------|------|
| 6 轴坐标结构 | `trapq.h` — `struct coord` 扩展 a/b/c 字段 |
| 6 轴梯形队列 | `trapq.c` — `trapq_append()` 20 参数，含 ABC |
| ABC 轴标志 | `itersolve.h` — `AF_A`, `AF_B`, `AF_C` 位标志 |
| ABC 轴求解 | `itersolve.c` — `check_active()` 支持 ABC |
| ABC 步进回调 | `kin_cartesian.c` — `cart_stepper_a/b/c_calc_position()` |
| FFI 更新 | `__init__.py` — Python-C 接口 20 参数 `trapq_append` |

### 2.3 Python 层扩展

| 功能 | 文件 |
|------|------|
| 7 轴 commanded_pos | `toolhead.py` — 动态扩展，ABC-only 移动检测 |
| 6 坐标步进计算 | `stepper.py` — `calc_position_from_coord` 传 6 坐标 |
| ABC G28 归零 | `homing.py` — homing_axes `"xyzabc"`，动态 force_axes |
| 批量接口修复 | `gcode_move.py` — G92/M114/SAVE/RESTORE 全轴支持 |
| `_fill_coord` 修复 | `homing.py` — thcoord 长度不足的 IndexError |

### 2.4 RTCP 特有功能

| 功能 | 说明 |
|------|------|
| TIP↔PIVOT 坐标变换 | `_apply_rtcp()` / `_apply_inverse_rtcp()` |
| gcode_move 变换链 | RTCP 在 gcode_move 层做变换，toolhead 无感知 |
| 笔尖弧长速度补偿 | `_adjust_move_d_for_rotary()` — 旋转时自动调整速度预算 |
| 旋转轴索引适配 | BC 配置自动跳过 A 轴索引 |
| pivot 偏移补偿 | pivot_x/pivot_y/pivot_z 支持 B/C 旋转中心机械偏差 + C轴偏心 |

---

## 3. 修改文件清单 (对比原版 Klipper)

### 3.1 新增文件 (21 个)

#### 运动学模块

| 文件 | 行数 | 说明 |
|------|------|------|
| `klippy/kinematics/cartesian_abc.py` | 134 | 通用多轴笛卡尔运动学 (XYZABC + E) |
| `klippy/kinematics/cartesian_rtcp.py` | 289 | RTCP 运动学 (TIP↔PIVOT 变换 + 速度补偿) |

#### 测试配置 & 用例

| 文件 | 说明 |
|------|------|
| `test/klippy/five_axis.cfg` | 7 轴测试配置 (XYZABCE, cartesian_abc) |
| `test/klippy/five_axis.test` | 五轴基础冒烟测试 |
| `test/klippy/six_axis_pulse.test` | XYZABC 脉冲精度测试 |
| `test/klippy/seven_axis_basic.test` | 7 轴单轴移动冒烟测试 |
| `test/klippy/seven_axis_pulse.test` | 7 轴脉冲精度测试 |
| `test/klippy/seven_axis_combined.test` | 7 轴组合移动测试 |
| `test/klippy/seven_axis_homing.test` | 7 轴归零测试 |
| `test/klippy/rtcp.cfg` | RTCP BC 测试配置 |
| `test/klippy/rtcp_basic.test` | RTCP 功能验证测试 |
| `test/klippy/rtcp_pulse.test` | RTCP 五轴联动脉冲精度测试 |
| `test/klippy/rtcp_pivot.cfg` | RTCP pivot 偏移测试配置 (px=5,py=10) |
| `test/klippy/rtcp_pivot.test` | RTCP pivot 偏移脉冲精度验证 |

#### 真机测试工具链

| 文件 | 说明 |
|------|------|
| `real_machine_test/printer.cfg` | 标准 BC RTCP 配置文件模板 |
| `real_machine_test/run_test.sh` | 一键测试管理脚本 |
| `real_machine_test/send_gcode.py` | G-code PTY 发送工具 |
| `real_machine_test/test_00_safety_check.gcode` | 阶段 0: 安全预检 |
| `real_machine_test/test_01_single_axis.gcode` | 阶段 1: 单轴验证 |
| `real_machine_test/test_02_homing.gcode` | 阶段 2: 归零测试 |
| `real_machine_test/test_03_rtcp_basic.gcode` | 阶段 3: RTCP 基础 |
| `real_machine_test/test_04_five_axis.gcode` | 阶段 4: 五轴联动 |
| `real_machine_test/test_05_drawing.gcode` | 阶段 5: 画线测试 |
| `real_machine_test/xPainter.cfg` | 校准宏 (含 C 轴偏心标定) |
| `real_machine_test/xPainter_test_marco.cfg` | 渐进式 RTCP 测试宏 (含 C 轴偏心验证) |

### 3.2 修改文件 (13 个)

#### C 层核心 (6 个)

| 文件 | 改动 |
|------|------|
| `klippy/chelper/itersolve.h` | 新增 `AF_A/B/C` 枚举，`itersolve_set_position` 9 参数，`calc_position_from_coord` 7 参数 |
| `klippy/chelper/itersolve.c` | `check_active()` 检查 a/b/c 轴，`itersolve_is_active_axis()` 响应 'a'/'b'/'c' |
| `klippy/chelper/trapq.h` | `struct coord` 扩展 a/b/c，`struct pull_move` 扩展 start_*/axes_r，`trapq_append` 20 参数 |
| `klippy/chelper/trapq.c` | `move_get_coord()` 返回 ABC，`trapq_set_position()` 设置 ABC，`copy_pull_move()` 复制 ABC |
| `klippy/chelper/kin_cartesian.c` | 新增 `cart_stepper_a/b/c_calc_position()`，`cartesian_stepper_alloc()` 支持 a/b/c 轴参数 |
| `klippy/chelper/__init__.py` | FFI 定义更新：`trapq_append` 20 参数，`struct pull_move` 含 ABC 字段 |

#### Python 层 (7 个)

| 文件 | 改动 |
|------|------|
| `klippy/toolhead.py` | `commanded_pos` 4→7 动态扩展，`trapq_append` 20 参数，ABC-only 移动检测 |
| `klippy/stepper.py` | `set_position()` / `calc_position_from_coord()` 传递完整 6 坐标 |
| `klippy/extras/gcode_move.py` | `axis_map` 扩展 ABC，G92/M114/GET_POSITION/SAVE/RESTORE 全轴支持 |
| `klippy/extras/homing.py` | G28 支持 ABC，`home_rails()` homing_axes `"xyzabc"`，`_fill_coord()` 修复 |
| `klippy/extras/force_move.py` | SET_KINEMATIC_POSITION 读 A/B/C，全 7 元素位置传递 |
| `klippy/kinematics/rotary_delta.py` | `itersolve_calc_position_from_coord` 调用更新为 7 参数 (兼容性修复) |

---

## 4. 架构说明

### 4.1 坐标空间

```
G-code (TIP空间)              显示 (TIP空间)
      |                             ^
      v                             |
  gcode_move (G92 偏移)    rtcp.get_position()
      |                             ^
      v                             |
  rtcp._apply_rtcp()       rtcp._apply_inverse_rtcp()
  (TIP → PIVOT)            (PIVOT → TIP)
      |                             ^
      v                             |
  toolhead (PIVOT空间) ─────────────┘
      |
      v
  trapq → itersolve → stepcompress → MCU → 步进电机
```

- **TIP 空间**: 用户编程的笔尖坐标，G-code 中的 X/Y/Z 值
- **PIVOT 空间**: B/C 轴旋转中心的机械坐标，步进电机实际位置

### 4.2 commanded_pos 内存布局

```
索引:  0    1    2    3    4    5    6
轴:   X    Y    Z    E    A    B    C
```

`_pos_idx` 映射将 rail 索引转换为此布局中的索引，处理 E 轴在索引 3 的特殊位置。

### 4.3 BC RTCP 公式

```
B = B 轴角度 (绕 Y 俯仰), C = C 轴角度 (绕 Z 旋转), L = tool_length

TIP → PIVOT (RTCP):
  X_pivot = X_tip - L · sin(B) · cos(C)
  Y_pivot = Y_tip - L · sin(B) · sin(C)
  Z_pivot = Z_tip + L · cos(B)

PIVOT → TIP (逆 RTCP):
  X_tip = X_pivot + L · sin(B) · cos(C)
  Y_tip = Y_pivot + L · sin(B) · sin(C)
  Z_tip = Z_pivot - L · cos(B)
```

### 4.4 速度模型

原始 Klipper 的 `Move.move_d` 仅用 XYZ 三轴计算路径长度。RTCP 扩展后:

1. `_adjust_move_d_for_rotary()` 通过逆 RTCP 还原 TIP 空间坐标
2. 计算 `effective_d = sqrt(ΔXYZ_tip² + (L·ΔB_rad)² + (L·ΔC_rad)²)`
3. 按 `effective_d / move_d` 比例缩放所有速度预算

确保纯旋转移动 (如 G1 B90) 时笔尖线速度正确匹配 F 值。

---

## 5. 回归测试

通过 12 个测试用例 (`scripts/test_klippy.py`):

| 测试 | 类型 |
|------|------|
| `seven_axis_basic.test` | 多轴冒烟 |
| `seven_axis_pulse.test` | 多轴脉冲精度 |
| `seven_axis_combined.test` | 多轴组合移动 |
| `seven_axis_homing.test` | 多轴归零 |
| `rtcp_basic.test` | RTCP 功能 |
| `rtcp_pulse.test` | RTCP 脉冲精度 |
| `five_axis.test` | 五轴基础 |
| `commands.test` | G-code 命令 |
| `extruders.test` | 挤出机 |
| `generic_cartesian.test` | 通用笛卡尔 |
| `linuxtest.test` | Linux 环境 |
| `macros.test` | 宏命令 |

---

## 6. 已知限制

| 问题 | 优先级 | 说明 |
|------|--------|------|
| G2/G3 圆弧 + 旋转轴 | 未实现 | 圆弧插补不支持 ABC 轴同步旋转 |
| G43 工具长度 | 待实现 | 运行时动态修改 tool_length (已写入备忘录) |
| Probe + 旋转轴 | 未实现 | 倾斜状态下的探针测量 |
| C 文件调试输出 | 低 | stepcompress.c 等有 fprintf(stderr) 调试信息 |
| rotary_delta 测试 | 跳过 | 校准测试需要额外适配 |

---

## 7. 项目命名建议

本项目是 Klipper 的五轴 RTCP 扩展，面向油画 CNC 应用。以下命名供选择:

| 命名 | 说明 |
|------|------|
| **Klipper-RTCP** | 强调核心的 RTCP 旋转刀具中心点功能 |
| **Klipper-Painter** | 强调油画绘画应用场景 |
| **Klipper-5AXIS** | 强调五轴扩展能力 |
| **XPainter** | 简练，X=多轴 + Painter=绘画 (也是工作目录名) |
| **PaintNC** | 绘画数控 (Painting NC) |

**最终命名: `Klipper-xPainter`** — 保留 Klipper 前缀表明上游项目来源，xPainter 体现多轴油画定位。

---

## 8. 构建与开发

```bash
# 编译 C 辅助库
cd klippy/chelper && gcc -Wall -g -O2 -shared -fPIC -o c_helper.so \
  pyhelper.c serialqueue.c stepcompress.c steppersync.c \
  itersolve.c trapq.c pollreactor.c msgblock.c trdispatch.c \
  kin_cartesian.c kin_corexy.c kin_corexz.c kin_delta.c \
  kin_deltesian.c kin_polar.c kin_rotary_delta.c kin_winch.c \
  kin_extruder.c kin_shaper.c kin_idex.c kin_generic.c

# 运行回归测试
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ \
  test/klippy/rtcp_basic.test test/klippy/rtcp_pulse.test

# 真机测试
cd real_machine_test && ./run_test.sh start && ./run_test.sh test all
```

---

> 文档生成日期: 2026-05-24
