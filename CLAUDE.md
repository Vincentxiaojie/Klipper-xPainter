# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Klipper 是一个 3D 打印机固件项目，采用双核架构：
- **MCU 固件**（C 语言）：运行在嵌入式微控制器上，负责实时任务（步进脉冲生成、PWM 控制等）
- **Klippy 主机软件**（Python）：运行在通用计算机上，负责 G-code 解析、运动规划、配置管理等高层功能

## 构建与测试

### 环境准备

```bash
# 安装 Python 依赖
pip3 install --break-system-packages pyserial jinja2 pyyaml greenlet cffi

# 下载测试数据字典（用于回归测试）
wget -O /tmp/klipper-dict.tar.gz "https://github.com/user-attachments/files/25528058/klipper-dict-20260224.tar.gz"
mkdir -p dict && tar xfz /tmp/klipper-dict.tar.gz -C dict/
```

### 编译固件（Linux MCU 架构）

```bash
cd klipper

# 配置为 Linux process 架构
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

# 清理
make clean
```

### 运行测试

```bash
# 运行单个测试
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ test/klippy/commands.test

# 运行所有测试
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ test/klippy/*.test
```

### 运行 Klippy 主机软件

```bash
# 批量模式（生成 MCU 命令）
PYTHONPATH=klipper python3 klippy/klippy.py config/example-cartesian.cfg -i test.gcode -o test.serial -d out/klipper.dict

# 解析二进制输出
PYTHONPATH=klipper python3 klippy/parsedump.py out/klipper.dict test.serial > test.txt
```

## 项目架构

```
klipper/
├── src/                    # MCU 固件（C 代码）
│   ├── sched.c            # 调度器核心
│   ├── stepper.c          # 步进电机控制
│   ├── command.c          # 命令解析/编码
│   ├── avr/               # AVR 架构
│   ├── stm32/             # STM32 架构
│   ├── linux/             # Linux 用户空间进程
│   ├── rp2040/            # Raspberry Pi RP2040/RP235x
│   └── generic/           # 通用 HAL 辅助代码
├── klippy/                # 主机 Python 软件
│   ├── chelper/           # C 语言辅助库（步进生成、运动学）
│   │   ├── steppersync.c  # 步进脉冲生成
│   │   ├── trapq.c       # 梯形运动队列
│   │   └── itersolve.c   # 迭代求解器
│   └── extras/            # 可加载模块（加热器、传感器等）
├── test/klippy/           # 测试用例（.test + .cfg 文件对）
├── config/                # 示例打印机配置
└── docs/                  # 文档
```

## 关键设计

### DECL_* 宏机制（src/ctr.h）
- `DECL_INIT(func)` - 启动时执行一次
- `DECL_TASK(func)` - 周期性执行
- `DECL_SHUTDOWN(func)` - 紧急停机时执行

### 配置系统
1. **Kconfig**：选择硬件架构和编译选项
2. **printer.cfg**：用户级打印机配置（引脚连接、步进参数等）

### Linux MCU 特点
- 编译为普通 Linux 可执行文件
- 可访问主机 GPIO、I2C、SPI 等硬件
- 适合本地开发和调试
- 后续可扩展支持 STM32 等真实 MCU

## 后续五轴升级

五轴运动学代码将位于 `klippy/kinematics/` 和 `klippy/chelper/` 目录，需要关注：
- 运动学求解器接口（itersolve.c）
- 梯形运动队列（trapq.c）
- 配置系统中的运动学参数定义