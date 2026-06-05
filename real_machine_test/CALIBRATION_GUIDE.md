# xPainter 校准操作手册

## 命令速查

```
XP_CHANGE_TOOL    XP_TOOL_READY     # 换笔工作流
XP_TOOL_CAL       XP_TOOL_TOUCH     XP_TOOL_POINT    XP_TOOL_APPLY   # tool_length
XP_PIVOT_CAL      XP_PIVOT_TOUCH    XP_PIVOT_POINT   XP_PIVOT_APPLY  # pivot_y
XP_Z_CAL          XP_Z_TOUCH                                           # Z 零点
XP_CLEAR_Z_OFFSET                                                      # 安全清零
```

`POINT` = 手动 jog 笔尖对准墨点，执行此命令记录当前 XY 坐标。

---

## 换笔工作流（日常最常用）

### 第一步：启动换笔

```
XP_CHANGE_TOOL
```

机器自动抬笔、归零 BC 轴。提示你换笔头。

### 第二步：确认换笔

换好笔后：

```
XP_TOOL_READY
```

自动进入 tool_length 标定流程（等同于执行 XP_TOOL_CAL）。

### 第三步：打点

机器移到工作区中心，提示你下探触纸。手动降 Z 到笔尖刚好接触纸面，然后：

```
XP_TOOL_TOUCH
```

机器自动打两个点：
- 点1：B=0（垂直）
- 点2：B=30（倾斜 30°）

### 第四步：对准点1

抬笔后，用控制台 jog 按钮把笔尖对准**点1**（B=0 打的点），然后：

```
XP_TOOL_POINT
```

显示 `点1 已记录 (x1, y1)`。

### 第五步：对准点2

继续 jog 笔尖对准**点2**（B=30 打的点），然后：

```
XP_TOOL_POINT
```

显示计算结果：
```
Δx = 3.2 mm  Δy = 0.1 mm
ΔL = 6.4 mm
当前 tool_length = 48.8 mm
推荐 tool_length = 55.2 mm
确认应用? 执行 XP_TOOL_APPLY
```

### 第六步：应用

```
XP_TOOL_APPLY
```

自动清零 Z offset（安全保护），更新 tool_length。提示执行 SAVE_CONFIG。

### 第七步：保存并重启

```
SAVE_CONFIG
```

然后重启 Klipper。

### 第八步：标定新 Z 零点

重启后，笔尖已经变了，必须重新标定纸面 Z 零点：

```
XP_Z_CAL      # 显示提示
```

手动降 Z 到笔尖刚好接触纸面，然后：

```
XP_Z_TOUCH    # 设当前位置为 Z=0
SAVE_CONFIG   # 持久化
```

换笔完成 ✅。

---

## 独立校准命令

### 仅标定 tool_length（不换笔）

```
XP_TOOL_CAL → 下探触纸 → XP_TOOL_TOUCH
  → jog 对准点1 → XP_TOOL_POINT
  → jog 对准点2 → XP_TOOL_POINT
  → XP_TOOL_APPLY
```

### 仅标定 pivot_y（C 轴偏心）

```
XP_PIVOT_CAL → 下探触纸 → XP_PIVOT_TOUCH
  → jog 对准点1 → XP_PIVOT_POINT
  → jog 对准点2 → XP_PIVOT_POINT
  → XP_PIVOT_APPLY
```

### 仅标定 Z 零点

```
XP_Z_CAL → 下探触纸 → XP_Z_TOUCH → SAVE_CONFIG
```

### 微调 Z 零点（Web 面板）

在 Mainsail/Fluidd 的 Z Offset 面板 ±0.1mm 微调，确认后执行 `SAVE_CONFIG`。

### 清零 Z Offset（安全）

```
XP_CLEAR_Z_OFFSET
```

> 通常在 tool_length 变化后必须执行，防止笔尖撞纸面。
> `XP_TOOL_APPLY` 会自动调用此命令。

---

## 画笔方向约束

| B 角度 | 笔尖位置 | 安全画线方向 |
|--------|---------|-------------|
| B > 0 | 笔尖在右 | X 递减（从右往左，← 拖着走） |
| B = 0 | 垂直居中 | 任意方向 |
| B < 0 | 笔尖在左 | X 递增（从左往右，→） |

生成的 G-code 和手动测试宏都必须遵守此规则。

---

## 公式原理

### tool_length 修正

```
L_new = L_current + Δx / sin(B_angle)

B=30° 时 sin(30°)=0.5，所以 L_new = L_current + 2*Δx
```

### pivot_y 修正

```
pivot_y_new = -Δx / sin(C_angle)

C=30° 时 sin(30°)=0.5，所以 pivot_y_new = -2*Δx
```
