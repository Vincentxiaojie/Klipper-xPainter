# 油画 CNC — BC RTCP 真机测试指南

## 文件清单

```
real_machine_test/
├── run_test.sh                    # 一键测试脚本（启动/停止/发送/收集）
├── send_gcode.py                  # G-code 发送工具
├── printer.cfg                    # 标准配置文件（需修改 pin 等参数）
├── test_00_safety_check.gcode     # 阶段0: 安全预检
├── test_01_single_axis.gcode      # 阶段1: 单轴手动验证
├── test_02_homing.gcode           # 阶段2: 归零测试
├── test_03_rtcp_basic.gcode       # 阶段3: RTCP 基础验证
├── test_04_five_axis.gcode        # 阶段4: 五轴联动
├── test_05_drawing.gcode          # 阶段5: 画线测试
└── README.md                      # 本文件
```

---

## 快速开始

```bash
cd ~/klipper/real_machine_test

# 1. 修改配置（搜索 <<< 替换为实际 pin）
nano printer.cfg

# 2. 启动 Klipper
./run_test.sh start

# 3. 确认运行正常
./run_test.sh status

# 4. 按顺序执行测试（逐条交互模式，每步按 Enter 确认）
./run_test.sh test 0    # 安全预检
./run_test.sh test 1    # 单轴验证
./run_test.sh test 2    # 归零测试
./run_test.sh test 3    # RTCP 基础验证 ⭐
./run_test.sh test 4    # 五轴联动
./run_test.sh test 5    # 画线测试

# 5. 收集结果打包
./run_test.sh collect

# 6. 停止 Klipper
./run_test.sh stop
```

---

## run_test.sh 命令参考

| 命令 | 说明 |
|------|------|
| `./run_test.sh start` | 后台启动 Klipper，日志写入 `/tmp/klippy.log` |
| `./run_test.sh stop` | 停止 Klipper |
| `./run_test.sh status` | 查看 Klipper 是否运行、端口是否就绪 |
| `./run_test.sh log` | 实时查看日志 (`tail -f`) |
| `./run_test.sh test 0` | 执行阶段 0 测试（交互模式，逐条确认） |
| `./run_test.sh test all` | 依次执行全部 6 个阶段（每阶段间暂停） |
| `./run_test.sh send -i test_xx.gcode` | 交互模式发送指定 G-code 文件 |
| `./run_test.sh send test_xx.gcode` | 连续模式发送（不暂停，用于自动化） |
| `./run_test.sh cmd "M115"` | 发送单条 G-code 命令 |
| `./run_test.sh collect` | 收集配置、日志、测试文件打包到 `test_results_*/` |

---

## send_gcode.py 命令参考

交互模式（推荐，每条命令等 Enter 确认再发下一条）:
```bash
python3 send_gcode.py -i test_03_rtcp_basic.gcode
```

连续模式（全部自动发送，适合跑完整个文件）:
```bash
python3 send_gcode.py test_03_rtcp_basic.gcode
```

发送单条命令:
```bash
python3 send_gcode.py -c "G28 X Y Z"
```

交互模式快捷键:
- **Enter** — 发送当前命令
- **s** — 跳过当前命令
- **r** — 重新显示上一条响应
- **q** — 退出

---

## 准备步骤

### 1. 修改 printer.cfg

搜索 `<<<` 找到所有需要修改的位置:

| 参数 | 说明 |
|------|------|
| `[mcu] serial` | 串口设备路径，`ls /dev/serial/by-id/*` 查看 |
| `[stepper_*] step_pin` | 步进脉冲 pin |
| `[stepper_*] dir_pin` | 方向 pin（方向反了加 `!` 前缀） |
| `[stepper_*] enable_pin` | 使能 pin |
| `[stepper_*] endstop_pin` | 限位开关 pin（`^` 常开，`!` 常闭） |
| `rotation_distance` | 电机转一圈移动距离（线性 mm，旋转 360） |
| `position_max` | 各轴最大行程 |
| `tool_length` | **B 轴旋转中心到笔尖距离 (mm)，需实测** |
| `position_endstop` | 限位开关触发位置的坐标值 |

### 2. 验证配置文件语法

```bash
python3 ~/klipper/klippy/klippy.py printer.cfg --import-test
```

### 3. 确认 Python 路径

如果默认 `python3` 不在 `klippy-env` 虚拟环境中，设置环境变量:
```bash
export KLIPPY_ENV=~/klippy-env/bin/python
```

---

## 测试流程

**按顺序执行，每个阶段通过后再进入下一阶段。**

### 阶段 0: 安全预检 (5 分钟)

文件: `test_00_safety_check.gcode`

逐条发送 M115、QUERY_ENDSTOPS、STEPPER_BUZZ 等命令。

**通过标准:**
- M115 返回 Klipper 版本信息
- QUERY_ENDSTOPS 能看到所有 endstop 状态（手动触发后变 triggered）
- STEPPER_BUZZ 每个电机震动且只有对应的那个震动
- STATUS 显示 `cartesian_rtcp` 运动学

### 阶段 1: 单轴手动验证 (10 分钟)

文件: `test_01_single_axis.gcode`

每个轴 ±5mm（线性）/ ±5°（旋转）微动，确认方向和距离。

**通过标准:**
- 各轴正/负方向移动正确
- 移动距离大致准确

**方向反了:** 修改 `[stepper_*]` 的 `dir_pin`，加 `!` 前缀。重启 Klipper 重新测试。

### 阶段 2: 归零测试 (5 分钟)

文件: `test_02_homing.gcode`

先归 Z（抬笔），再逐个归 XYBC，最后全部归零。

**通过标准:**
- 每个轴: 向 endstop 移动 → 触发 → 回退 → 停止
- 全部归零顺序正确，无碰撞
- 归零后 STATUS 显示 `homed_axes: xyzbc`

### 阶段 3: RTCP 基础验证 (15 分钟) ⭐ 核心

文件: `test_03_rtcp_basic.gcode`

**测试方法:** 笔尖下方放纸，标记笔尖位置。倾斜/旋转后检查笔尖是否还在标记位置。

**通过标准:**
- B=15°/30° 倾斜: 笔尖位置不变（目测 < 0.5mm）
- C=45°/90° 旋转: 笔尖位置不变
- B=30°+C=90° 组合: 笔尖位置不变
- M114 显示的 tip 坐标不变

**笔尖移动了:** `tool_length` 不准，实测后修正，重启 Klipper 重测。

### 阶段 4: 五轴联动 (5 分钟)

文件: `test_04_five_axis.gcode`

XYZ+BC 同时运动，验证轨迹平滑度和同步精度。

**通过标准:**
- 五轴同时运动轨迹平滑，无抖动
- 加减速流畅，无异响
- M114 终点坐标与预期一致

### 阶段 5: 画线测试 (15 分钟)

文件: `test_05_drawing.gcode`

**准备:** A4 纸、笔/颜料、直尺/卡尺

**通过标准:**
- 5.1 vs 5.2: 竖直画线和倾斜画线位置偏差 < 1mm
- 5.3: B=15°/30°/45° 起笔点重合
- 5.4: C=0°/45°/90° 线宽有变化，但起笔位置不变
- 5.5: 圆形规则，直径约 40mm
- 5.6: 倾斜画圆仍是圆形（非椭圆）
- 5.7: 四个方格位置水平对齐

---

## 结果记录

每阶段测试后填写（纸笔或电子均可）:

```
阶段 X: [通过 / 不通过]
观察到的问题:
M114 显示坐标:
备注:
```

---

## 提交分析

### 自动收集

```bash
./run_test.sh collect
```

会在 `real_machine_test/test_results_YYYYMMDD_HHMMSS/` 下生成:
- `printer.cfg` — 最终配置
- `klippy.log` — 完整日志
- `test_0*.gcode` — 测试 G-code 副本
- `summary.txt` — 结果摘要模板（请填写）

### 手动收集

打包以上目录 + 以下文件发回分析:

1. **填写好的 `summary.txt`** — 每阶段通过情况
2. **画线照片** — 阶段 5 画线结果俯视图（旁边放直尺做参照）
3. **异常视频** — 如有抖动、异响、运动异常，录短视频

```bash
# 打包
tar czf test_results.tar.gz -C real_machine_test test_results_YYYYMMDD_HHMMSS/

# 加上照片
# (手动将照片复制到结果目录后再打包)
```

### 发送方式

将 `test_results.tar.gz` 和照片/视频通过对话发给我分析。
