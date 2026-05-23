# Klipper 测试框架文档

## 概述

Klipper 的测试框架用于验证固件和主机软件（Klippy）的正确性，支持：
- **单元测试**：验证 G-code 命令、温度控制、运动学等功能
- **回归测试**：确保代码修改不破坏现有功能
- **批量模式**：将 G-code 文件转换为 MCU 命令，用于分析或调试

---

## 测试环境搭建

### 1. 安装依赖

```bash
pip3 install --break-system-packages pyserial jinja2 pyyaml greenlet cffi
```

### 2. 下载测试数据字典

测试需要不同 MCU 平台的数据字典文件：

```bash
mkdir -p dict
wget -O /tmp/klipper-dict.tar.gz "https://github.com/user-attachments/files/25528058/klipper-dict-20260224.tar.gz"
tar xfz /tmp/klipper-dict.tar.gz -C dict/
```

### 3. 编译 Linux MCU 固件（如需）

```bash
cd klipper

# 配置为 Linux 架构
python3 -c "
import sys
sys.path.insert(0, 'lib/kconfiglib')
from kconfiglib import Kconfig
k = Kconfig('src/Kconfig')
for sym in k.defined_syms:
    if sym.name == 'MACH_LINUX':
        sym.set_value('y')
        break
k.write_config('.config')
"

# 编译
make
```

---

## 运行测试

### 基本命令

```bash
# 运行单个测试文件
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ test/klippy/commands.test

# 运行多个测试文件
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ test/klippy/commands.test test/klippy/extruders.test

# 运行所有测试
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ test/klippy/*.test
```

### 常用选项

| 选项 | 说明 |
|------|------|
| `-d dict/` | 指定数据字典目录 |
| `-v` | 显示完整输出（verbose） |
| `-k` | 保留临时文件（默认会删除） |
| `-t tempdir` | 指定临时文件目录 |

### 示例

```bash
# 显示完整输出
PYTHONPATH=klipper python3 scripts/test_klippy.py -v -d dict/dict/ test/klippy/commands.test

# 保留临时文件用于调试
PYTHONPATH=klipper python3 scripts/test_klippy.py -k -v -d dict/dict/ test/klippy/commands.test
```

---

## 测试文件格式

测试文件是 `.test` 文本文件，每行包含一个 G-code 命令或测试指令：

```
DICTIONARY linuxprocess.dict    # 指定数据字典
CONFIG linuxtest.cfg            # 指定配置文件

G4 P1000                        # G-code 命令
G28                             # 归零
M104 S100                       # 设置挤出机温度
```

### 关键指令

| 指令 | 说明 |
|------|------|
| `DICTIONARY <file>` | 指定 MCU 数据字典文件（必须） |
| `CONFIG <file>` | 指定打印机配置文件 |
| `GCODE <file>` | 从文件读取 G-code（替代内联命令） |
| `SHOULD_FAIL` | 期望测试失败（用于验证错误处理） |

---

## 测试用例列表

共 **36** 个测试文件，覆盖以下功能：

### 运动控制
| 测试文件 | 测试内容 |
|----------|----------|
| `commands.test` | 通用 G-code 命令（M114, M115, G28, G92 等） |
| `extruders.test` | 挤出机控制、挤出偏转 |
| `generic_cartesian.test` | 标准笛卡尔运动学 |
| `polar.test` | 极坐标运动学 |
| `corexyuv.test` | CoreXYUV 运动学 |
| `delta.test` | Delta 运动学 |
| `z_tilt.test` | Z 轴倾斜补偿 |
| `multi_z.test` | 多 Z 轴电机 |
| `quad_gantry_level.test` | 四轴龙门调平 |
| `screws_tilt_adjust.test` | 螺丝倾斜调整 |
| `manual_stepper.test` | 手动步进电机控制 |
| `input_shaper.test` | 输入整形器（振动补偿） |
| `pressure_advance.test` | 压力推进调谐 |
| `gcode_arcs.test` | G2/G3 圆弧插补 |
| `out_of_bounds.test` | 边界检查 |

### 温度控制
| 测试文件 | 测试内容 |
|----------|----------|
| `temperature.test` | 加热器温度控制（ M104, M109, M140 等） |

### 传感器
| 测试文件 | 测试内容 |
|----------|----------|
| `bed_mesh.test` | 热床网格调平 |
| `bltouch.test` | BLTouch 探针 |
| `eddy.test` | 涡流传感器 |
| `load_cell.test` | 称重传感器 |
| `z_virtual_endstop.test` | 虚拟 Z 终点挡块 |
| `endstop_phase.test` | 限位开关相位 |

### 辅助功能
| 测试文件 | 测试内容 |
|----------|----------|
| `macros.test` | 宏命令 |
| `led.test` | LED 控制 |
| `pwm.test` | PWM 输出 |
| `sdcard_loop.test` | SD 卡循环打印 |
| `tmc.test` | TMC 步进驱动 |
| `printers.test` | 打印机配置验证 |
| `exclude_object.test` | 对象排除 |
| `dual_carriage.test` | 双拖船 |
| `hybrid_corexy_dual_carriage.test` | 混合 CoreXY 双拖船 |

### 特定架构
| 测试文件 | 测试内容 |
|----------|----------|
| `linuxtest.test` | Linux MCU 特定测试 |

---

## 批量模式：G-code 转 MCU 命令

### 生成数据字典

首先需要编译 MCU 代码生成字典：

```bash
make menuconfig
make
```

编译后会在 `out/klipper.dict` 生成数据字典。

### 转换 G-code

```bash
# 将 G-code 文件转换为 MCU 命令
PYTHONPATH=klipper python3 klippy/klippy.py config/example-cartesian.cfg \
    -i test.gcode -o test.serial -d out/klipper.dict

# 解析为可读文本
PYTHONPATH=klipper python3 klippy/parsedump.py out/klipper.dict test.serial > test.txt
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `-i test.gcode` | 输入 G-code 文件 |
| `-o test.serial` | 输出二进制 MCU 命令 |
| `-d out/klipper.dict` | 数据字典文件 |

---

## 调试工具

### 查看日志

```bash
# Klippy 日志默认输出到 stderr，可重定向
PYTHONPATH=klipper python3 klippy/klippy.py config/example-cartesian.cfg -l /tmp/klippy.log
```

### 提取调试信息

```bash
# 从日志提取配置和错误信息
mkdir work_directory
cd work_directory
cp /tmp/klippy.log .
python3 scripts/logextract.py klippy.log
```

### 运动数据分析

```bash
# 启动 API Server
PYTHONPATH=klipper python3 klippy/klippy.py config/example-cartesian.cfg -a /tmp/klippy_uds

# 记录运动数据
python3 scripts/motan/data_logger.py /tmp/klippy_uds mylog -s '*'

# 生成图表
python3 scripts/motan/motan_graph.py mylog -o mygraph.png
```

---

## 常见问题

### 测试失败：找不到数据字典

```bash
# 确保数据字典已下载
ls dict/dict/*.dict | head -5
```

### 测试失败：配置错误

检查 `.test` 文件中的 `CONFIG` 和 `DICTIONARY` 路径是否正确。

### MCU 命令错误

检查 `out/klipper.dict` 是否与编译固件版本匹配，必要时重新编译。

---

## 测试流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     测试执行流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 准备阶段                                                │
│     ├── 安装 Python 依赖                                    │
│     └── 下载数据字典                                        │
│                                                             │
│  2. 编译固件（可选）                                        │
│     ├── make menuconfig                                    │
│     └── make                                               │
│                                                             │
│  3. 运行测试                                                │
│     ├── 单个测试: test_klippy.py xxx.test                  │
│     ├── 多个测试: test_klippy.py test1.test test2.test     │
│     └── 所有测试: test_klippy.py test/klippy/*.test       │
│                                                             │
│  4. 分析结果                                                │
│     ├── 通过: "All N test cases passed"                    │
│     └── 失败: "Test case xxx FAILED (reason)"              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 后续扩展

- **五轴运动学测试**：在 `klippy/kinematics/` 添加新运动学后，需创建对应的 `.test` 和 `.cfg` 文件
- **新传感器支持**：在 `klippy/extras/` 添加传感器模块后，参考现有传感器测试创建测试用例
- **STM32 MCU 测试**：配置 `CONFIG_MACH_STM32=y` 编译后，使用相应数据字典运行测试