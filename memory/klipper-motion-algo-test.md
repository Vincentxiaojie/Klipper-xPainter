---
name: klipper-motion-algo-test
description: Klipper 运动算法修改后的测试方法论：test_klippy.py + stepstats.py 的完整闭环验证方案
metadata:
  type: reference
  originSessionId: 2174e9f0-2220-4266-8469-e914790aaee6
---

# Klipper 运动算法测试方法论

## 什么时候用这个方案

修改 `klippy/kinematics/` Python 逻辑或 `klippy/chelper/` C 语言高频阶梯生成算法时，必须用此方案验证正确性。

**优先级**：test_klippy.py + stepstats.py >> SimulAVR

---

## 四步验证法

### 第一步：创建测试用例

在 `klippy/test/klippy/` 创建 `.test` 文件，例如 `my_algo_test.test`：

```text
config:
  [mcu]
  serial: /dev/ttyS0
  [printer]
  kinematics: cartesian
  max_velocity: 300
  max_accel: 3000
  [stepper_x]
  step_pin: PA5
  dir_pin: PA4
  enable_pin: !PA6
  microsteps: 16
  rotation_distance: 40
  position_endstop: 0
  position_max: 200

gcode:
  G28 X0          ; 先复位
  G1 X100 F6000   ; 以 100mm/s 移动 100mm
```

### 第二步：计算理论脉冲数

以配置 `rotation_distance=40`, `microsteps=16` 为例：

- 步进电机原生步数：200 步/圈（1.8度电机）
- 每毫米脉冲数 = (200 × 16) ÷ 40 = **80 脉冲/mm**
- 目标移动距离：100mm
- **理论总脉冲数 = 80 × 100 = 8000 个脉冲**

### 第三步：运行 test_klippy.py + stepstats.py

```bash
# 运行测试，输出二进制指令
python scripts/test_klippy.py test/klippy/my_algo_test.test -o _my_out.serial -d test/dicts

# 分析脉冲数
python scripts/stepstats.py _my_out.serial
```

**核对输出表格**：

```
Axis        | Count   | Min Interval | Max Interval | ...
stepper_x   | 8000    | 0.000125     | 0.002500     | ...
```

- Count = 8000 ✅ 算法整体位移总量精确
- Count = 7999/8002 ❌ 浮点数取整/累加/减速点边界处理有 Bug

### 第四步：检查梯形加减速波形

从 stepstats.py 输出的 Min Interval 验证速度是否超速：

- 理论最高速：F6000 = 100mm/s
- 每秒脉冲数：100 × 80 = 8000 脉冲/秒
- **理论最小脉冲间隔 = 1 ÷ 8000 = 0.000125 秒**

如果 Min Interval 远小于 0.000125（如 0.00005），说明算法在某个瞬间让速度超速飙升，会导致电机失步。

---

## 何时需要 SimulAVR

| 情况 | 用什么 |
|------|--------|
| test_klippy.py 脉冲数异常 | 先修算法 Bug，不用 SimulAVR |
| 脉冲数正常但打印机报错 | 用 SimulAVR 检查 MCU 定时器负担 |
| 算法计算量太大导致 Timer too close | SimulAVR 观察 CPU 使用率和硬件定时器寄存器 |

---

## 关键脚本位置

- `klippy/scripts/test_klippy.py` - Klipper 测试运行器
- `klippy/scripts/stepstats.py` - 脉冲统计/速度分析工具

---

## 为什么比 SimulAVR 更好

1. **更快** - 不需要模拟整个 AVR 指令周期
2. **更准** - 直接验证 Klipper 发出的脉冲数量，而非 MCU 实际处理结果
3. **更容易定位** - 脉冲数不对说明算法逻辑错，定时器太近说明 C 代码效率问题