# RTCP 渐进式画线测试指南

借鉴工业 RTCP 验证标准（NAS 979 锥台、球测试、锥形运动），设计 6 级递进真机测试。

## 准备工作

1. A4 白纸放在工作台面
2. 装好画笔，笔尖调至离纸面约 5mm
3. Klipper 控制台执行 `G28` 归零后，手动 `G1 Z5` 微调高度
4. 确认 `printer.cfg` 中 `tool_length` 已实测校准（当前: 173mm）

## 测试金字塔

```
TEST_RTCP_FULL     — 5点两轮打点验收 (XYZBC 全五轴)     [终极]
TEST_RTCP_CIRCLE   — 倾斜画 φ30 圆对比 (XYZBC 全五轴)   [Level 5]
TEST_RTCP_SQUARE   — 倾斜画 30mm 方框对比 (XYZB 四轴)   [Level 4]
TEST_RTCP_C_ROTATE — C 旋转画线对比 (XYC 三轴)          [Level 3]
TEST_RTCP_B_TILT   — B 俯仰画线对比 (XZ 两轴)           [Level 2]
TEST_RTCP_BASELINE — 纯 XYZ 基线 (无 RTCP)              [Level 1]
```

每级在纸上留下可见痕迹，通过对比 B=0/C=0 基线和倾斜姿态的结果判断 RTCP 精度。

---

## TEST_RTCP_BASELINE — 纯 XYZ 基线

| 项目 | 说明 |
|------|------|
| **轴数** | XYZ (3 线性轴，无旋转轴) |
| **目的** | 确认基本画线功能正常，建立对比基线 |
| **画线** | X 方向直线 50mm → Y 方向直线 50mm → 中心点 |
| **预期** | 纸上出现十字线 + 中心点标记 |
| **失败** | 线不直/电机方向反 → 检查 dir_pin；画不出 → 笔太高 |

```
G-code 流程:
  _RTCP_HOME_AND_ZERO      # 归零→笔尖Z=5→G92(0,0,0)
  _PEN_DOWN                # 降笔
  G1 X50 F600              # 画X线
  _PEN_UP                  # 抬笔
  G1 X0 F3000              # 回原点
  _PEN_DOWN
  G1 Y50 F600              # 画Y线
  _PEN_UP
  G1 Y0 F3000
  _PEN_DOWN                # 中心打点
  G4 P500
  _PEN_UP
```

---

## TEST_RTCP_B_TILT — B 俯仰画线

| 项目 | 说明 |
|------|------|
| **轴数** | X + Z + B (B 轴俯仰时 XZ 联动补偿) |
| **目的** | 验证 B 轴倾斜后笔尖 Z 高度和 X 位置是否正确补偿 |
| **画线** | B=0 画 X 线 → B=15 再画 → B=25 再画 → B=-15 再画 |
| **预期** | **4 条线完全重合**（同一位置同一方向） |
| **判定** | 倾斜线偏移 → `tool_length` 不准确，重新实测 |
| **原理** | B 倾斜时笔尖几何关系: X_pivot += L·sin(B), Z_pivot += L·cos(B) |

```
G-code 流程:
  _RTCP_HOME_AND_ZERO
  # 线1: B=0 基线
  _PEN_DOWN → G1 X50 → _PEN_UP → G1 X0
  # 线2: B=15 倾斜
  G1 B15 F400 → _PEN_DOWN → G1 X50 → _PEN_UP → G1 X0
  # 线3: B=25 大倾角
  G1 B25 F400 → _PEN_DOWN → G1 X50 → _PEN_UP → G1 X0
  # 线4: B=-15 反向俯仰
  G1 B-15 F400 → _PEN_DOWN → G1 X50 → _PEN_UP
  G1 B0 X0 F600            # 回正
```

---

## TEST_RTCP_C_ROTATE — C 旋转画线

| 项目 | 说明 |
|------|------|
| **轴数** | X + Y + C (C 轴旋转时 XY 联动补偿) |
| **目的** | 验证 C 旋转后笔尖 XY 位置不变，仅笔头方向变化 |
| **画线** | C=0 画 X 线 → C=30 → C=-30 → B=15 + C=30 |
| **预期** | **4 条线位置重合，但线宽逐条变化**（笔头方向变了） |
| **判定** | 线位置偏移 → C 轴中心未校准；线宽不变 → C 旋转机构不工作 |

```
G-code 流程:
  _RTCP_HOME_AND_ZERO
  _PEN_DOWN → G1 X50 → _PEN_UP → G1 X0   # C=0
  G1 C30 → _PEN_DOWN → G1 X50 → _PEN_UP → G1 X0
  G1 C-30 → _PEN_DOWN → G1 X50 → _PEN_UP → G1 X0
  G1 B15 C30 → _PEN_DOWN → G1 X50 → _PEN_UP
  G1 B0 C0 X0 F600
```

---

## TEST_RTCP_SQUARE — 倾斜画方框

| 项目 | 说明 |
|------|------|
| **轴数** | X + Y + Z + B (B 倾斜时 XYZ 三轴联动补偿) |
| **目的** | 验证倾斜姿态下平面图形的保真度 |
| **画线** | B=0 画 30×30mm 正方形 → B=20 再画 → B=-15 再画 |
| **预期** | **3 个方框完全重合**（位置、大小、形状一致） |
| **判定** | 方框放大/缩小 → Z 步进不准；平行四边形 → 轴垂直度问题 |

```
G-code 流程:
  _RTCP_HOME_AND_ZERO
  # 框1: B=0
  _PEN_DOWN
  G1 X30 F600 → G1 Y30 → G1 X0 → G1 Y0   # 30×30mm 正方形
  _PEN_UP
  # 框2: B=20
  G1 B20 → _PEN_DOWN
  G1 X30 F600 → G1 Y30 → G1 X0 → G1 Y0
  _PEN_UP
  # 框3: B=-15
  G1 B-15 → _PEN_DOWN
  G1 X30 F600 → G1 Y30 → G1 X0 → G1 Y0
  _PEN_UP
  G1 B0 F600
```

---

## TEST_RTCP_CIRCLE — 倾斜画圆

| 项目 | 说明 |
|------|------|
| **轴数** | X + Y + Z + B + C (全部 5 轴同时运动) |
| **目的** | 验证全五轴联动下的圆弧精度 |
| **画线** | B=0 画 φ30 圆 (24段 G1) → B=20 再画同一个圆 |
| **预期** | **两个圆完全重合**，圆形不应变为椭圆 |
| **判定** | 变椭圆 → XY 步进需校准；平移 → tool_length 不准 |
| **实现** | 圆用 24 段 G1 逼近（每段 15°），因 G2/G3 不支持 ABC 参数 |

```
G-code 流程:
  _RTCP_HOME_AND_ZERO
  G1 X15 Y0 F3000           # 移到圆心右侧 (圆心偏移半径)
  # 圆1: B=0, 24段 G1 从 0°→360°
  _PEN_DOWN
  G1 X29.49 Y3.88 F600
  G1 X27.99 Y7.50
  ... (共24段, 每15度)
  G1 X30.00 Y0.00           # 闭合
  _PEN_UP
  # 圆2: B=20, 同样 24 段
  G1 X15 Y0 F3000
  G1 B20 F400
  _PEN_DOWN
  ... (同24段)
  _PEN_UP
  G1 B0 X0 Y0 F600
```

---

## TEST_RTCP_FULL — 多点打点验收

| 项目 | 说明 |
|------|------|
| **轴数** | X + Y + Z + B + C (全部 5 轴) |
| **目的** | RTCP 精度终极验证 — 两组点应完全重合 |
| **参考点** | 中心 (0,0)、右 (25,0)、前 (25,25)、左 (0,25)、回中心 (0,0) |
| **打点** | 第1轮: B=0 C=0 打 5 个点 → 第2轮: B=15 C=20 重访打点 |
| **预期** | **两轮 5 点阵完全重合** (每个点打两次在同一位置) |
| **判定** | 不重合 → 综合检查 tool_length, B/C 中心, XY 步进 |

```
G-code 流程:
  _RTCP_HOME_AND_ZERO
  # 第1轮: B=0 C=0 打5个参考点
  中心(0,0)→右(25,0)→前(25,25)→左(0,25)→回中心(0,0)
  每点: _PEN_DOWN → G4 P500 → _PEN_UP

  # 第2轮: B=15 C=20 RTCP打点
  G1 B15 C20 F400
  重复同样5个点
  每点: _PEN_DOWN → G4 P500 → _PEN_UP

  G1 B0 C0 F600            # 回正
```

---

## 验证流程

### 操作步骤

```
Klipper 控制台:
  TEST_RTCP_BASELINE    # 1. 先画基线，确认电机方向正确
  TEST_RTCP_B_TILT      # 2. B俯仰线应重合
  TEST_RTCP_C_ROTATE    # 3. C旋转线位置同一，线宽变化
  TEST_RTCP_SQUARE      # 4. 方框应重合
  TEST_RTCP_CIRCLE      # 5. 圆应重合，不变椭圆
  TEST_RTCP_FULL        # 6. 两轮点应重合
```

### 通过标准

| 测试宏 | 合格线 | 说明 |
|--------|--------|------|
| BASELINE | 线画得出 | 基础功能 |
| B_TILT | 线偏差 < 0.5mm | 裸眼可辨 |
| C_ROTATE | 线偏差 < 0.5mm | C 角度应改变线宽 |
| SQUARE | 方框偏差 < 0.5mm | 形状应保持正方 |
| CIRCLE | 圆偏差 < 0.5mm | 不应变椭圆 |
| FULL | 点偏差 < 0.3mm | 终极精度 |

### 失败诊断矩阵

| 症状 | 可能原因 | 修复 |
|------|---------|------|
| B_TILT 倾斜线偏移 | `tool_length` 不准 | 重新实测 B 轴旋转中心到笔尖距离 |
| C_ROTATE 线宽不变 | C 轴不转 | 检查 stepper_c 连接/使能 |
| SQUARE 方框变梯形 | X/Y 轴不垂直 | 检查机械装配 |
| CIRCLE 圆变椭圆 | X/Y 步进比例不准 | `rotation_distance` 需校准 |
| FULL 两轮点不重合 | B/C 中心偏移 | 检查旋转中心与工具中心对准 |
| 任何级画不出线 | 笔太高 | 增大 `_PEN_DOWN` 的 Z 下移量 |

---

## 辅助宏说明

| 宏名 | 作用 | 调整项 |
|------|------|--------|
| `_RTCP_HOME_AND_ZERO` | 归零→移到 X100 Y100→笔尖 Z=5→设 G92 零点 | Z5 可改为其他高度 |
| `_RTCP_SHOW_POS` | 输出 M114 + GET_POSITION | 诊断用 |
| `_PEN_DOWN` | 相对下移 Z-5 (降笔) | 笔触不到就改大，如 Z-8 |
| `_PEN_UP` | 相对上移 Z5 (抬笔) | 需与 _PEN_DOWN 对称 |

> **命名规则**: Klipper 的 `[gcode_macro]` 名称不能包含数字（如 `_2AXIS`），否则 G-code 解析器会把数字当参数拆开。

---

## 工业参考

本测试设计参考以下工业标准:

- **NAS 979**: 锥台切削测试 (1969)，五轴验收基准
- **ISO 10791-6**: 加工中心速度和插补精度标准
- **ISO 10791-7:2020**: 含 S 形试件 (Annex)
- **球测试 (Sphere Test)**: Heidenhain KinematicsOpt, Siemens CYCLE996
- **Tsutsumi 方锥台**: 可识别 7 种几何误差源
- **画线对比法**: 最直观的现场 RTCP 验证方法
