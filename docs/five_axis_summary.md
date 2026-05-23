# Klipper 五轴运动学扩展 - 阶段性总结

## 一、做了哪些修改

### 1. C 层扩展（6轴支持）

| 文件 | 修改内容 |
|------|---------|
| `klippy/chelper/itersolve.h` | 添加 `AF_A`, `AF_B`, `AF_C` 轴标志 (第 28-30 行) |
| `klippy/chelper/itersolve.c` | 扩展 `check_active()` 和 `itersolve_is_active_axis()` 支持 ABC 轴 |
| `klippy/chelper/trapq.h` | `struct coord` 从 5 轴扩展到 6 轴 (x,y,z,a,b,c) |
| `klippy/chelper/trapq.c` | `move_get_coord()`, `trapq_append()`, `trapq_set_position()` 更新 |

**关键改动**：`trapq_append` 从 17 参数扩展到 20 参数，新增 A/B/C 轴的位置和速率参数。

### 2. Python 层扩展

| 文件 | 修改内容 |
|------|---------|
| `klippy/chelper/__init__.py` | FFI 定义更新为 20 参数的 `trapq_append` |
| `klippy/toolhead.py` | `trapq_append` 调用更新（第 284-291, 471-478 行） |
| `klippy/extras/force_move.py` | `trapq_append` 调用修复（第 83-86 行，少一个参数已补上） |
| `klippy/extras/manual_stepper.py` | `trapq_append` 调用更新（第 68-72, 175-179 行） |
| `klippy/kinematics/extruder.py` | `trapq_append` 调用更新（第 250-254 行） |
| `klippy/kinematics/cartesian_abc.py` | **新建** - 多轴笛卡尔运动学（支持 XYZABC 动态检测） |

### 3. 新建文件

- `klippy/kinematics/cartesian_abc.py` - 五轴笛卡尔运动学实现
- `test/klippy/five_axis.cfg` - 五轴配置文件
- `test/klippy/five_axis.test` - 五轴基础测试用例
- `test/klippy/simulavr_five_axis.test` - Simulavr 五轴联动测试

---

## 二、怎样搭建测试环境

### 1. 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt-get install gcc-avr avr-libc binutils-avr
sudo apt-get install g++ make cmake swig python3-dev
```

### 2. 编译安装 simulavr

```bash
# 克隆 simulavr
cd /home/alpha
git clone git://git.savannah.nongnu.org/simulavr.git simulavr
cd simulavr

# 修复 CMakeLists.txt（避免 check-modtest 错误）
sed -i 's/add_dependencies(check check-extinttest check-modtest check-timertest)/# add_dependencies(check check-extinttest check-modtest check-timertest)/' CMakeLists.txt

# 配置和编译
rm -rf build && mkdir build && cd build
cmake .. -DBUILD_PYTHON=ON
make -j4

# 验证 Python 模块
ls pysimulavr/_pysimulavr*.so
```

### 3. 下载 Klipper 测试字典

```bash
cd /home/alpha/xpainter/klipper
wget -O /tmp/klipper-dict.tar.gz "https://github.com/user-attachments/files/25528058/klipper-dict-20260224.tar.gz"
mkdir -p dict && tar xfz /tmp/klipper-dict.tar.gz -C dict/
```

### 4. 编译 Klipper AVR 固件

```bash
cd /home/alpha/xpainter/klipper

# 配置为 ATmega644p + Simulavr
python3 -c "
import sys
sys.path.insert(0, 'lib/kconfiglib')
from kconfiglib import Kconfig
k = Kconfig('src/Kconfig')
for sym in k.defined_syms:
    if sym.name == 'MACH_ATMEGA644P': sym.set_value('y')
    if sym.name == 'SIMULAVR': sym.set_value('y')
k.write_config('.config')
"

# 编译
make clean && make -j4
```

---

## 三、怎样测试

### 1. 启动 Simulavr（终端 1）

```bash
cd /home/alpha/xpainter/klipper
PYTHONPATH=/home/alpha/simulavr/build/pysimulavr/ \
./scripts/avrsim.py out/klipper.elf
```

启动后会显示：
```
Starting AVR simulation: machine=atmega644 speed=16000000
Serial: port=/tmp/pseudoserial baud=250000
```

### 2. 运行测试（终端 2）

```bash
cd /home/alpha/xpainter/klipper

# 基础测试
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ \
    test/klippy/simulavr_five_axis.test

# 单个配置文件测试
PYTHONPATH=klipper python3 scripts/test_klippy.py -d dict/dict/ \
    test/klippy/commands.test
```

---

## 四、测试了哪些内容

### 1. 基础命令测试
- `STATUS` - 状态查询
- `M105` - 温度读取
- `M114` - 位置查询

### 2. Homing 测试
- `G28` - 轴归零

### 3. 五轴联动测试
- `G1 X10 A90` - X 轴移动 10mm，A 轴旋转 90°

### 4. 回归测试（确保现有功能不受影响）
- `manual_stepper.test`
- `dual_carriage.test`
- `generic_cartesian.test`
- `delta.test`
- `corexyuv.test`
- `commands.test`

---

## 五、测试结果如何看

### 1. 成功输出
```
Starting test/klippy/simulavr_five_axis.test (generic-simulavr.cfg)

    All 1 test cases passed
```

### 2. 失败输出
```
Test case test/klippy/xxx.test FAILED (error message)!

Traceback (most recent call last):
  ...
```

### 3. Simulavr 日志
查看 `/tmp/avrsim.log` 可以看到 MCU 仿真的详细输出：
```bash
tail -f /tmp/avrsim.log
```

### 4. Klippy 日志
运行时添加 `-v` 参数查看详细输出：
```bash
PYTHONPATH=klipper python3 scripts/test_klippy.py -v -d dict/dict/ test/klippy/xxx.test
```

---

## 六、已知问题

1. **ABC 轴在 toolhead.py 中硬编码为 0** - 联动测试通过但实际 ABC 运动未传递到 trapq
2. **multi_z.test 配置错误** - `z_tilt z_positions needs exactly 0 items`，与五轴扩展无关
3. **ATmega2560 不支持 Simulavr** - 如需测试 Mega 2560 需用真实硬件

---

## 七、下一步工作

1. 修复 `toolhead.py` 中 ABC 轴参数传递
2. 实现逆运动学（将旋转角度转换为步进位置）
3. 编写更复杂的五轴联动测试用例

---

## 八、关键文件路径速查

| 用途 | 路径 |
|------|------|
| Simulavr 源码 | `/home/alpha/simulavr/` |
| pysimulavr 模块 | `/home/alpha/simulavr/build/pysimulavr/` |
| Klipper 源码 | `/home/alpha/xpainter/klipper/` |
| 测试字典 | `/home/alpha/xpainter/klipper/dict/dict/` |
| 五轴运动学 | `klippy/kinematics/cartesian_abc.py` |
| 五轴测试 | `test/klippy/simulavr_five_axis.test` |
| pseudo-serial 设备 | `/tmp/pseudoserial` |