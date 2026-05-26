#!/bin/bash
# ============================================================
# run_test.sh — 一键启动 Klipper + 测试流程
# ============================================================
# 用法:
#   ./run_test.sh start         启动 Klipper 后台运行
#   ./run_test.sh stop          停止 Klipper
#   ./run_test.sh status        查看 Klipper 运行状态
#   ./run_test.sh send <file>   发送 G-code 文件
#   ./run_test.sh send -i <file> 交互模式逐条发送
#   ./run_test.sh cmd "G28 X"   发送单条命令
#   ./run_test.sh log           查看实时日志
#   ./run_test.sh test <阶段>   执行指定测试阶段 (0-5)
#   ./run_test.sh test all      依次执行所有测试阶段
#   ./run_test.sh collect       收集测试结果打包
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KLIPPY_DIR="$HOME/Klipper-xPainter"
KLIPPY="$KLIPPY_DIR/klippy/klippy.py"
SEND_GCODE="$SCRIPT_DIR/send_gcode.py"
PRINTER_CFG="$SCRIPT_DIR/printer.cfg"
LOG_FILE="/tmp/klippy.log"
PID_FILE="/tmp/klippy.pid"
PORT="/tmp/printer"

# Python 环境
PYTHON="${KLIPPY_ENV:-python3}"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

banner() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[X]${NC} $1"; }

# ============================================================
# 启动 Klipper
# ============================================================
do_start() {
    banner "启动 Klipper"

    # 检查配置文件
    if [ ! -f "$PRINTER_CFG" ]; then
        error "配置文件不存在: $PRINTER_CFG"
        exit 1
    fi

    # 检查是否已经运行
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        warn "Klipper 已在运行 (PID: $(cat $PID_FILE))"
        exit 0
    fi

    # 清理旧的端口文件
    rm -f "$PORT" "$PID_FILE"

    # 启动 Klipper
    info "启动命令: $PYTHON $KLIPPY $PRINTER_CFG -I $PORT -l $LOG_FILE"
    $PYTHON "$KLIPPY" "$PRINTER_CFG" -I "$PORT" -l "$LOG_FILE" &
    KLIPPY_PID=$!
    echo $KLIPPY_PID > "$PID_FILE"

    # 等待 PTY 创建
    info "等待 Klipper 初始化..."
    for i in $(seq 1 30); do
        if [ -e "$PORT" ]; then
            info "Klipper 已启动 (PID: $KLIPPY_PID, 端口: $PORT)"
            info "日志文件: $LOG_FILE"
            echo ""
            echo -e "${GREEN}现在可以发送 G-code:${NC}"
            echo "  $0 send -i test_00_safety_check.gcode"
            echo "  $0 cmd \"M115\""
            echo "  $0 log"
            exit 0
        fi
        sleep 1
    done

    error "Klipper 启动超时，请检查日志: $LOG_FILE"
    exit 1
}

# ============================================================
# 停止 Klipper
# ============================================================
do_stop() {
    banner "停止 Klipper"

    if [ ! -f "$PID_FILE" ]; then
        warn "PID 文件不存在，尝试查找进程..."
        pkill -f "klippy/klippy.py" 2>/dev/null || true
        exit 0
    fi

    PID=$(cat $PID_FILE)
    if kill -0 "$PID" 2>/dev/null; then
        info "正在停止 Klipper (PID: $PID)..."
        kill "$PID"
        sleep 2
        if kill -0 "$PID" 2>/dev/null; then
            warn "强制终止..."
            kill -9 "$PID" 2>/dev/null || true
        fi
        info "Klipper 已停止"
    else
        warn "进程 $PID 已不存在"
    fi

    rm -f "$PID_FILE"
}

# ============================================================
# 状态
# ============================================================
do_status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
        info "Klipper 运行中 (PID: $(cat $PID_FILE))"
        echo "  端口: $PORT"
        echo "  日志: $LOG_FILE"
        if [ -e "$PORT" ]; then
            info "串口 $PORT 已就绪"
        fi
    else
        warn "Klipper 未运行"
    fi
}

# ============================================================
# 发送 G-code
# ============================================================
do_send() {
    if [ ! -e "$PORT" ]; then
        error "串口 $PORT 不存在，请先启动 Klipper: $0 start"
        exit 1
    fi
    $PYTHON "$SEND_GCODE" "$@"
}

# ============================================================
# 发送单条命令
# ============================================================
do_cmd() {
    if [ ! -e "$PORT" ]; then
        error "串口 $PORT 不存在，请先启动 Klipper: $0 start"
        exit 1
    fi
    $PYTHON "$SEND_GCODE" -c "$1"
}

# ============================================================
# 查看日志
# ============================================================
do_log() {
    if [ ! -f "$LOG_FILE" ]; then
        warn "日志文件不存在: $LOG_FILE"
        exit 1
    fi
    echo "[*] 实时日志 (Ctrl+C 退出)"
    tail -f "$LOG_FILE"
}

# ============================================================
# 执行测试阶段
# ============================================================
do_test() {
    local stage="$1"

    if [ ! -e "$PORT" ]; then
        error "请先启动 Klipper: $0 start"
        exit 1
    fi

    case "$stage" in
        0)
            banner "阶段 0: 安全预检"
            warn "请逐条发送以下命令，观察反馈"
            echo ""
            $PYTHON "$SEND_GCODE" -i "$SCRIPT_DIR/test_00_safety_check.gcode"
            ;;
        1)
            banner "阶段 1: 单轴手动验证"
            warn "逐条执行，确认每个轴方向正确后继续"
            echo ""
            $PYTHON "$SEND_GCODE" -i "$SCRIPT_DIR/test_01_single_axis.gcode"
            ;;
        2)
            banner "阶段 2: 归零测试"
            warn "确保各轴附近无障碍物"
            echo ""
            $PYTHON "$SEND_GCODE" -i "$SCRIPT_DIR/test_02_homing.gcode"
            ;;
        3)
            banner "阶段 3: RTCP 基础验证"
            echo ""
            echo "  准备: 笔尖下方放纸，标记笔尖位置"
            echo "  方法: 执行倾斜/旋转后，检查笔尖是否还在标记位置"
            echo ""
            $PYTHON "$SEND_GCODE" -i "$SCRIPT_DIR/test_03_rtcp_basic.gcode"
            ;;
        4)
            banner "阶段 4: 五轴联动"
            echo ""
            $PYTHON "$SEND_GCODE" -i "$SCRIPT_DIR/test_04_five_axis.gcode"
            ;;
        5)
            banner "阶段 5: 画线测试"
            echo ""
            echo "  准备: A4纸 + 笔/颜料 + 直尺/卡尺"
            echo "  执行后用量具测量画线结果"
            echo ""
            $PYTHON "$SEND_GCODE" -i "$SCRIPT_DIR/test_05_drawing.gcode"
            ;;
        all)
            for s in 0 1 2 3 4 5; do
                echo ""
                echo ""
                read -p "按 Enter 开始阶段 $s ..." _
                do_test $s
                echo ""
                read -p "阶段 $s 完成。按 Enter 继续下一阶段 ..." _
            done
            banner "全部测试完成!"
            ;;
        *)
            error "未知阶段: $stage (可选: 0-5, all)"
            exit 1
            ;;
    esac
}

# ============================================================
# 收集测试结果
# ============================================================
do_collect() {
    banner "收集测试结果"

    OUTPUT_DIR="$SCRIPT_DIR/test_results_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$OUTPUT_DIR"

    info "输出目录: $OUTPUT_DIR"

    # 复制配置
    cp "$PRINTER_CFG" "$OUTPUT_DIR/"
    info "已复制: printer.cfg"

    # 复制日志
    if [ -f "$LOG_FILE" ]; then
        cp "$LOG_FILE" "$OUTPUT_DIR/"
        info "已复制: klippy.log"
    else
        warn "日志文件不存在"
    fi

    # 复制测试 G-code
    cp "$SCRIPT_DIR"/test_0*.gcode "$OUTPUT_DIR/" 2>/dev/null || true
    info "已复制: 测试 G-code 文件"

    # 生成摘要
    cat > "$OUTPUT_DIR/summary.txt" << EOF
============================================================
油画 CNC BC RTCP 真机测试结果
============================================================
测试时间: $(date '+%Y-%m-%d %H:%M:%S')
配置:    printer.cfg (附)
日志:    klippy.log (附)
============================================================

阶段 0 - 安全预检:      [ ] 通过  [ ] 不通过
阶段 1 - 单轴验证:      [ ] 通过  [ ] 不通过
阶段 2 - 归零测试:      [ ] 通过  [ ] 不通过
阶段 3 - RTCP 基础:     [ ] 通过  [ ] 不通过
阶段 4 - 五轴联动:      [ ] 通过  [ ] 不通过
阶段 5 - 画线测试:      [ ] 通过  [ ] 不通过

问题记录:
------------------------------------------------------------

M114 读数记录:
------------------------------------------------------------

画线测量结果:
------------------------------------------------------------

备注:
------------------------------------------------------------

EOF

    info "摘要模板: $OUTPUT_DIR/summary.txt (请填写)"
    echo ""
    echo "============================================================"
    echo "  结果目录: $OUTPUT_DIR"
    echo "  发给开发者分析:"
    echo "    tar czf test_results.tar.gz -C $(dirname $OUTPUT_DIR) $(basename $OUTPUT_DIR)"
    echo "============================================================"
}

# ============================================================
# 主入口
# ============================================================
case "${1:-}" in
    start)   do_start ;;
    stop)    do_stop ;;
    status)  do_status ;;
    send)    shift; do_send "$@" ;;
    cmd)     do_cmd "$2" ;;
    log)     do_log ;;
    test)    do_test "${2:-all}" ;;
    collect) do_collect ;;
    *)
        echo "用法: $0 <命令> [参数]"
        echo ""
        echo "命令:"
        echo "  start                   启动 Klipper 后台运行"
        echo "  stop                    停止 Klipper"
        echo "  status                  查看运行状态"
        echo "  send <file>             发送 G-code 文件"
        echo "  send -i <file>          交互模式逐条发送 G-code"
        echo "  cmd \"<gcode>\"            发送单条 G-code 命令"
        echo "  log                     查看实时日志"
        echo "  test <阶段>              执行测试 (0-5, all)"
        echo "  collect                 收集测试结果打包"
        echo ""
        echo "测试流程:"
        echo "  1. $0 start              # 启动 Klipper"
        echo "  2. $0 status             # 确认运行"
        echo "  3. $0 test 0             # 安全预检"
        echo "  4. $0 test 1             # 单轴验证"
        echo "  5. $0 test 2             # 归零测试"
        echo "  6. $0 test 3             # RTCP 基础验证"
        echo "  7. $0 test 4             # 五轴联动"
        echo "  8. $0 test 5             # 画线测试"
        echo "  9. $0 collect            # 收集结果"
        echo " 10. $0 stop               # 停止 Klipper"
        ;;
esac
