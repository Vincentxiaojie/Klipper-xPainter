# Simulavr VCD 脉冲测试状态

## 当前状态：VCD 数据未捕获到步进脉冲

### 测试结果

1. **VCD 文件仅包含头信息，无实际信号变化**
2. **仿真时间正常推进**（VCD 时间戳显示约 972ms 的仿真时间）
3. **测试命令正常执行**（G28 + 4 次 G1 运动共 200mm 距离）

### 根本原因分析

1. **Simulavr 的 VCD 追踪机制问题**：
   - VCD 数据仅在 `dman.stopApplication()` 时写入
   - 步进脉冲变化太快（16MHz 时钟），simulavr 仿真环境无法实时跟踪
   - 需要 investigation of klipper 固件中 stepper.c 的实现

2. **VCD 波形文件特性**：
   - 328 字节 = 仅有头部（无数据变化）
   - 353 字节 = 头部 + PORT/PIN 寄存器（但无 A5-Out 变化）
   - 正确格式应为 > 10KB 包含数千个信号变化沿

### 已验证可用的配置

- 测试命令：`G28` (归位) + `G1 X50 F1200` + `G1 X0 F1200` (往复运动)
- 配置文件：`config/generic-simulavr.cfg`
- 固件：`out/klipper.elf` (atmega644)
- 信号：`PORTA.A5-Out` (X 轴 step), `PORTA.A4-Out` (X 轴 dir), `PORTA.A1-Out` (enable)

### 建议的替代方案

**方法一：使用 Klipper 自带的 stepstats.py**
```bash
python3 scripts/stepstats.py <serial_log>
```

**方法二：使用 vcdvcd 进行自动化计数**
```bash
pip3 install vcdvcd
vcdvcd step_pulses.vcd --signal PORTA.A5-Out
```

**方法三：直接分析 MCU 命令流**
- 捕获 klipper 发送给 MCU 的二进制命令
- 解析 `queue_step` 命令来统计脉冲数

### 下一步建议

1. 使用真实硬件（Mega2560）进行脉冲测试
2. 或者修改 klipper 固件添加软件仿真友好的调试输出
3. 使用 Linux MCU 架构（`make LINUX=m`）进行本地测试