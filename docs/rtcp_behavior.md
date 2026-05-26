# RTCP 多轴联动行为说明

## 机械结构

油画 CNC 采用 BC 型 RTCP 结构：

- **B 轴**：绕 Y 轴俯仰，控制笔尖倾斜角度（笔杆与台面夹角）
- **C 轴**：绕 Z 轴旋转，控制长方形笔头方向
- **B/C 旋转中心（pivot point）**：两个旋转轴的交点
- **工具长度 L**（`tool_length`）：从旋转中心到笔尖的距离

```
        pivot (B/C 旋转中心)
         |
         |  L (tool_length)
         |
        tip (笔尖)
```

## 两个坐标空间

RTCP 系统维护两套坐标空间：

| 空间 | 含义 | 使用者 |
|------|------|--------|
| TIP 空间 | 笔尖坐标（用户 G-code 编写的位置） | G-code move, M114, GET_POSITION |
| PIVOT 空间 | 旋转中心坐标（toolhead 内部的机械坐标） | toolhead.move, trapq, stepper |

`gcode_move` 的 transform 链在每次 `G1` 时将 TIP→PIVOT，在每次 `M114` / `GET_POSITION` 时将 PIVOT→TIP。

## M114 为何显示 XYZ 不变

执行 `G1 B20 C20` 后物理 XYZ 电机会动，但 M114 显示 XYZ 不变——**这是 RTCP 的正确行为**。

### 完整数据流

设 tool_length = 80，当前在 `X=50, Y=100, Z=10, B=0, C=0`：

```
G1 B20 C20 F400
  │
  ├─ gcode_move 更新 TIP 坐标: (50, 100, 10, B=20, C=20)
  │
  ├─ cartesian_rtcp.move() → _apply_rtcp()  TIP→PIVOT:
  │   X_pivot = 50 + 80·sin(20°)·cos(20°) = 50 + 25.71 = 75.71
  │   Y_pivot = 100 + 80·sin(20°)·sin(20°) = 100 + 9.36 = 109.36
  │   Z_pivot = 10 + 80·cos(20°) = 10 + 75.18 = 85.18
  │
  ├─ toolhead.move(75.71, 109.36, 85.18, ...)  — XYZBC 电机运动
  │
  └─ M114 → get_position() → _apply_inverse_rtcp()  PIVOT→TIP:
      X_tip = 75.71 - 80·sin(20°)·cos(20°) = 75.71 - 25.71 = 50  ← 不变
      Y_tip = 109.36 - 80·sin(20°)·sin(20°) = 109.36 - 9.36 = 100 ← 不变
      Z_tip = 85.18 - 80·cos(20°) = 85.18 - 75.18 = 10            ← 不变
      B/C tip = 20/20 ← 反映当前角度
```

正向变换和逆向变换精确互逆，所以 M114 的 XYZ 必然等于之前 G-code 设定的 TIP 坐标。

### 如何看到真实的 PIVOT 位置

`GET_POSITION` 命令会输出多个层级的位置信息：

```
GET_POSITION
# stepper:  步进电机原始坐标（PIVOT 空间）
# kinematic: 运动学模块 calc_position() 结果
# toolhead:  toolhead.get_position() 结果（TIP 空间）
# gcode:     M114 同款（TIP 空间）
```

对比 `toolhead`/`gcode`（TIP 空间，XYZ 不变）和 `stepper`/`kinematic`（PIVOT 空间，XYZ 已偏移）即可确认 RTCP 在工作。

## RTCP 数学公式 (BC 配置)

### TIP → PIVOT（正向变换，`_apply_rtcp`）

```
X_pivot = X_tip + L · sin(B) · cos(C)
Y_pivot = Y_tip + L · sin(B) · sin(C)
Z_pivot = Z_tip + L · cos(B)
```

### PIVOT → TIP（逆向变换，`_apply_inverse_rtcp`）

```
X_tip = X_pivot - L · sin(B) · cos(C)
Y_tip = Y_pivot - L · sin(B) · sin(C)
Z_tip = Z_pivot - L · cos(B)
```

## 为什么 G1 B 会移动 XYZB 四个轴

当执行 `G1 B20` 时，用户要求在 TIP 空间保持笔尖位置不变，仅改变 B 轴角度。

**G-code 处理**：`gcode_move.cmd_G1` 更新 `last_position[5] = 20`（TIP 空间坐标），然后调用 `move_with_transform(last_position, speed)`。

**RTCP 变换**：`cartesian_rtcp.move()` 调用 `_apply_rtcp(pos)`，根据公式将 TIP 坐标转换为 PIVOT 坐标。B 从 0° 变为 20°，会改变 `sin(B)` 和 `cos(B)` 的值：

- `X_pivot` 变化量 = L · (sin(20°) - sin(0°)) · cos(C)
- `Y_pivot` 变化量 = L · (sin(20°) - sin(0°)) · sin(C)
- `Z_pivot` 变化量 = L · (cos(20°) - cos(0°))

因此 toolhead 收到的 `move` 指令是 PIVOT 空间的 XYZB 四轴同时移动。

### 示例

设 `tool_length = 80`, 当前 `B=0, C=0`：

| 命令 | TIP 空间 | PIVOT 空间（变换后） |
|------|----------|---------------------|
| `G1 B20` | `(0,0,0, B=20, C=0)` | `(0, 0, -4.86, B=20)` → XYZB 联动 |

Z pivot 移动 -4.86mm，保持笔尖在台面上不动。

## 为什么 G1 C 在 B=0 vs B≠0 时表现不同

执行 `G1 C20`：

| B 当前角度 | sin(B) | PIVOT 空间变化 | 移动的轴 |
|-----------|--------|---------------|---------|
| B = 0° | 0 | X、Y 不变 (sin(B)=0 使 X、Y pivot 项归零)，Z 不变 | 仅 C |
| B ≠ 0° | ≠ 0 | X、Y 随 cos(C)/sin(C) 变化 | XYC 三个轴 |

### 原因

X_pivot = X_tip + L · sin(B) · cos(C)，Y_pivot = Y_tip + L · sin(B) · sin(C)

- B=0 时 sin(B)=0，cos(C) 和 sin(C) 的变化被乘以 0，不影响 X/Y pivot → 仅 C 轴转动
- B≠0 时 sin(B)≠0，C 的变化通过 cos(C)/sin(C) 投影到 X/Y 轴 → XYC 联动

## 单独控制 B/C 电机

由于 RTCP 会自动补偿 XYZ，无法通过 `G1 B` / `G1 C` 单独移动旋转轴（除非 B=0 时的纯 C 旋转）。

### 方法一：FORCE_MOVE（推荐）

绕过 RTCP 变换，直接操作 step motor：

```
FORCE_MOVE STEPPER=stepper_b DISTANCE=5 VELOCITY=100   # B 轴电机旋转 5°
FORCE_MOVE STEPPER=stepper_c DISTANCE=5 VELOCITY=100   # C 轴电机旋转 5°
```

注意：FORCE_MOVE 直接操作步进电机，不更新运动学坐标。使用后需要用 `G28 B` / `G28 C` 重新归零。

### 方法二：暂时设置 tool_length=0

如果 tool_length 可通过 G-code 动态修改，设 L=0 可关闭 RTCP 补偿，使 `G1 B` / `G1 C` 仅移动旋转轴。

## `_adjust_move_d_for_rotary` 速度模型

RTCP 旋转轴专用速度调整：当 B/C 旋转导致笔尖弧线移动时，即使 TIP 空间 XYZ 坐标不变，笔尖实际走过的弧长为 L · Δθ_rad。此方法：

1. 通过逆 RTCP 恢复 TIP 空间位移
2. 计算旋转引起的弧长贡献：L · Δθ_rad
3. 将总有效路径长度（arc length + XYZ displacement）放缩到 move 的预算中

确保旋转轴大角度移动时运动平滑、速度受控。

## 验证方法

### 真机测试

```gcode
# 1. 验证 G1 B → XYZB 四轴联动
G28 X Y Z B C
G92 X0 Y0 Z0 B0 C0
G1 X100 Z80 F6000
G92 X100 Y0 Z80 B0 C0
M114                         # 记录初始 TIP 位置
G1 B20 F400                  # XYZB 应同时移动
M114                         # B=20，X/Y/Z tip 应不变

# 2. 验证 G1 C at B=0 → 仅 C 移动
G1 B0 F400
M114
G1 C30 F400                  # 仅 C 旋转
M114

# 3. 验证 G1 C at B≠0 → XYC 联动
G1 B20 F400
M114
G1 C60 F400                  # XYC 同时移动
M114

# 4. 验证 FORCE_MOVE 单独控制
FORCE_MOVE STEPPER=stepper_b DISTANCE=5 VELOCITY=100
```

### 自动化测试

```bash
PYTHONPATH=klipper python3 scripts/test_klippy.py \
  -d dict/dict/ \
  test/klippy/rtcp_basic.test test/klippy/rtcp_homing.test
```
