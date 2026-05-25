# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

> **跨机器记忆**: `memory/` 目录包含项目进度、设计决策和已知问题的持久化记忆。
> 在新机器上 clone 后，将这些文件复制或软链接到 `~/.claude/projects/<project-path>/memory/` 目录即可恢复上下文。

## 项目概述

**Klipper-xPainter** — 油画 CNC 五轴 RTCP 系统，基于 Klipper v0.13.0 的 fork。

- **仓库**: https://github.com/Vincentxiaojie/Klipper-xPainter (私有)
- **目标**: 3 线性轴 (XYZ) + 2 旋转轴 (BC) 的油画绘制 CNC，支持 RTCP (刀尖跟随)
- **BC 结构**: B 轴绕 Y 俯仰（笔尖倾斜），C 轴绕 Z 旋转（长方形笔头方向控制）
- **架构**: MCU 固件（C）+ Klippy 主机（Python），与上游 Klipper 一致

### 当前状态 (2026-05-26)

| 模块 | 状态 | 关键文件 |
|------|------|---------|
| 6-7 轴 C 层扩展 | ✅ 完成 | `chelper/itersolve.c`, `trapq.c`, `kin_cartesian.c` |
| Python 层多轴支持 | ✅ 完成 | `toolhead.py`, `stepper.py`, `gcode_move.py` |
| ABC 归零 (G28) | ✅ 完成 | `homing.py`, `kinematics/cartesian_abc.py` |
| G92/M114/GET_POSITION | ✅ 完成 | `extras/gcode_move.py` |
| RTCP 运动学 | ✅ 完成 | `kinematics/cartesian_rtcp.py` |
| RTCP 速度模型 | ✅ 完成 | `cartesian_rtcp.py:_adjust_move_d_for_rotary()` |
| 真机测试配置 | ✅ 完成 | `real_machine_test/printer.cfg` |
| G43 工具长度 | 🔧 待实现 | — |
| G2/G3 圆弧 ABC | 🔧 待设计 | — |

## 构建与测试

### 环境准备

```bash
pip3 install --break-system-packages pyserial jinja2 pyyaml greenlet cffi
wget -O /tmp/klipper-dict.tar.gz "https://github.com/user-attachments/files/25528058/klipper-dict-20260224.tar.gz"
mkdir -p dict && tar xfz /tmp/klipper-dict.tar.gz -C dict/
```

### 编译 chelper

```bash
cd klippy/chelper && gcc -Wall -g -O2 -shared -fPIC -o c_helper.so \
  pyhelper.c serialqueue.c stepcompress.c steppersync.c \
  itersolve.c trapq.c pollreactor.c msgblock.c trdispatch.c \
  kin_cartesian.c kin_corexy.c kin_corexz.c kin_delta.c \
  kin_deltesian.c kin_polar.c kin_rotary_delta.c kin_winch.c \
  kin_extruder.c kin_shaper.c kin_idex.c kin_generic.c
```

### 运行测试

```bash
# 单个测试
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ test/klippy/commands.test

# 全量（six_axis_pulse.test 耗时 464 秒，日常可跳过）
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ $(ls test/klippy/*.test | grep -v six_axis_pulse)
```

### 预存测试失败（非功能问题）

| 测试 | 原因 |
|------|------|
| `delta_calibrate.test` | Python 3.14 multiprocessing pickle 不兼容 |
| `rotary_delta_calibrate.test` | 同上 |
| `exclude_object.test` | Python 3.14 IndexError |
| `load_cell.test` | 缺少 numpy 模块 |
| `manual_stepper.test` | stepcompress 内部错误 (WSL) |
| `printers.test` | 多打印机 smoke test (WSL 环境) |
| `pulse_step.test` | WSL 环境问题 |
| `simulavr_step.test` | pin PA5 重复配置 |

## 关键设计

### 轴索引映射

当前 7 轴布局：`X=0, Y=1, Z=2, E=3, A=4, B=5, C=6`

`cartesian_abc.py` 中 `_pos_idx` 处理 E-at-index-3 偏移：stepper 列表中不含 E（E 由 extruder 模块单独管理），但 `commanded_pos` 包含 E。rails 索引需跳过 index 3。

### RTCP 架构

- **TIP 空间**: 用户 G-code 的笔尖坐标 → `gcode_move` transform 链中由 `rtcp.move()` 做 TIP→PIVOT 转换
- **PIVOT 空间**: 旋转中心的机器坐标 → `toolhead.move()` 直接接收，不感知 RTCP
- 归零在 PIVOT 空间完成（不调用 RTCP 变换）

### gcode_macro 覆盖内置命令 (重要)

`gcode.py:142` 已修改：`register_command` 对已注册命令从 `raise config_error` 改为 `debug log + 覆盖`。`stepper_enable` 自动注册 M18/M84 后，`[gcode_macro M18]` 可以覆盖。

**测试覆盖**: `test/klippy/macro_override.test` 专门验证此场景。

### 调试日志警告

`stepcompress.c`, `steppersync.c`, `itersolve.c` 等有大量 `fprintf(stderr, ...)` 调试输出。`six_axis_pulse.test` 因此产生巨大 I/O 阻塞（464 秒）。性能测试前需清理这些日志。

## 目录结构（仅关键文件）

```
klipper/
├── klippy/
│   ├── gcode.py               # [已修改] register_command 允许覆盖
│   ├── toolhead.py            # [已修改] 7轴 trapq_append, drip_move
│   ├── stepper.py             # [已修改] 6坐标 set_position
│   ├── chelper/               # C 辅助库 (6轴扩展)
│   │   ├── itersolve.c/h      # 迭代求解器 (+AF_A/B/C)
│   │   ├── trapq.c/h          # 梯形队列 (struct coord 6轴)
│   │   └── kin_cartesian.c    # 笛卡尔回调
│   ├── kinematics/
│   │   ├── cartesian_abc.py   # 多轴运动学 (含 G28 ABC)
│   │   └── cartesian_rtcp.py  # RTCP 运动学
│   └── extras/
│       ├── gcode_move.py      # G92/M114/GET_POSITION (ABC 扩展)
│       ├── homing.py           # G28 ABC + _fill_coord 修复
│       └── force_move.py      # SET_KINEMATIC_POSITION ABC
├── test/klippy/               # 测试用例
│   ├── macro_override.test    # gcode_macro 覆盖内置命令
│   ├── rtcp_basic.test        # RTCP 功能测试
│   ├── seven_axis_*.test      # 7轴测试 (4个)
│   └── five_axis.test         # 5轴基础测试
├── real_machine_test/         # 真机测试工具链
│   ├── printer.cfg            # 真机配置 (BC RTCP)
│   └── run_test.sh            # 测试启动脚本
├── config/                    # 上游示例配置
├── src/                       # MCU 固件
└── memory/                    # 跨机器持久化记忆
```