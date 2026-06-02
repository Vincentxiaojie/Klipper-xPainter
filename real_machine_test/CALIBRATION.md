# xPainter 校准指南

## 核心概念

### 两个坐标空间

| 空间 | 含义 | 举例 |
|------|------|------|
| **PIVOT** | B/C 轴旋转中心的机械坐标 | stepper 位置、toolhead.move |
| **TIP** | 笔尖坐标（你编写 G-code 的位置） | M114 显示、G1 X Y Z |

转换公式（B=0, C=0）：
```
Z_tip = Z_pivot - tool_length
```

### 两个关键参数

| 参数 | 含义 | 性质 | 配置位置 |
|------|------|------|---------|
| **tool_length** | B 轴旋转中心 → 笔尖的距离 | 机械常数，换笔才变 | `[printer] tool_length` |
| **Z 零点** | 纸面在机器坐标中的 Z 位置 | 纸张高度决定 | `CALIBRATE_Z_OFFSET` 宏 |

```
         Z_pivot = 250 (归零后)
         |
         |  ← B 轴旋转中心 (pivot)
         |  tool_length (固定机械距离)
         |  ← 笔尖 (tip)
    _____|_____  纸张 ← Z=0 (工作零点)
```

### 常见误解

❌ "归零后下探触纸，显示的 Z=124.6 就是 tool_length"
✅ 124.6 是 TIP 空间 Z 坐标，取决于当前 tool_length 设置和纸张高度。**不是** B 旋转中心到笔尖的距离。

---

## 标定流程

### 步骤 1：标定 tool_length（换笔时）

**原理**：B 轴倾斜法。如果 tool_length 正确，RTCP 会在 B 轴旋转时保持笔尖不动；如果 tool_length 有偏差，笔尖位置会随 B 角度变化。

```
ΔZ(B₁→B₂) = ΔL × (cos(B₂) − cos(B₁))
```

**操作**：

1. 执行 `CALIBRATE_TOOL_LENGTH`
2. 机器自动归零，B 轴归 0°
3. 手动 Jog Z 下探，直到**笔尖刚好触碰纸张**
4. 执行 `TOOL_CAL_NEXT`（记录位置，B 自动转到 30°）
5. 再次手动下探触纸（RTCP 已自动补偿，但如果 tool_length 不准笔尖会有偏移）
6. 执行 `TOOL_CAL_NEXT`（自动计算并报告推荐值）

**输出示例**：
```
[CAL] Z(B=0)=124.6  Z(B=30)=118.3
[CAL] ΔZ=-6.3mm  ΔL=47.0mm
[CAL] 当前 tool_length=124.8
[CAL] ★ 推荐 tool_length: 77.8 ★
[CAL] 请手动修改 printer.cfg 中 [printer] tool_length 后重启
```

7. 修改 `printer.cfg` 中 `[printer]` 段的 `tool_length` 为推荐值
8. 重启 Klipper：`FIRMWARE_RESTART`

### 步骤 2：标定 Z 工作零点（换纸时）

**操作**：

1. 执行 `G28` 归零所有轴
2. 手动 Jog Z 下探，直到**笔尖刚好触碰纸张**
3. 执行 `CALIBRATE_Z_OFFSET`
4. 控制台显示：`[CAL] Z零点已保存 (纸面=Z0)`

**之后**：Z=0 即代表纸面。`G1 Z5` 抬笔 5mm，`G1 Z0` 笔尖触纸。

### 自动恢复（每次重启）

执行 `G28` 后，Z 零点自动恢复。无需手动操作。

控制台会显示：`[CAL] Z零点已恢复 (纸面=Z0)`

若显示 "Z零点未标定"，说明尚未执行过 `CALIBRATE_Z_OFFSET`。

---

## 精度验证

标定完成后，执行以下 G-code 验证 RTCP 精度：

```gcode
G28                              # 归零，自动恢复 Z 零点
G1 X125 Y100 Z5 B0 C0 F3000      # 移动到画布中心上方 5mm
G1 Z0 F200                       # 笔尖触纸
_PEN_DOWN                         # 留一个点
_PEN_UP
G1 B20 F400                      # B 轴倾斜 20°
_PEN_DOWN                         # 应打在同一个点
_PEN_UP
G1 B0 F400                       # 回到垂直
```

如果 B=0 和 B=20 打出的点**完全重合**，说明 tool_length 标定准确。若偏移 < 0.5mm 属于正常。

---

## 配置参考

```
[printer]
kinematics: cartesian_rtcp
tool_length: 77.8     # ← 步骤1标定出的值
rotary_config: bc
pivot_x: 0
pivot_y: 0
pivot_z: 0

[save_variables]
filename: /home/alpha/Klipper-xPainter-data/saved_vars.cfg
```

---

## 宏速查

| 宏 | 用途 | 频率 |
|----|------|------|
| `CALIBRATE_TOOL_LENGTH` | 启动 tool_length 标定 | 换笔时 |
| `TOOL_CAL_NEXT` | 记录触纸位置（标定流程中） | 同上 |
| `CALIBRATE_Z_OFFSET` | 一键保存 Z 零点 | 换纸时 |
| `_RESTORE_Z_OFFSET` | 恢复 Z 零点（G28 自动调用） | 每次重启 |
