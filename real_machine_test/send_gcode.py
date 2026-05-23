#!/usr/bin/env python3
# ============================================================
# send_gcode.py — 向运行中的 Klipper 发送 G-code
# ============================================================
# 用法:
#   # 发送整个文件（连续模式）
#   python3 send_gcode.py test_01_single_axis.gcode
#
#   # 逐条发送（交互模式，每条等确认）
#   python3 send_gcode.py -i test_01_single_axis.gcode
#
#   # 发送单条命令
#   python3 send_gcode.py -c "G28 X Y Z"
#
#   # 指定串口路径
#   python3 send_gcode.py -p /tmp/printer test.gcode
# ============================================================

import argparse
import os
import sys
import time
import termios
import tty
import select

DEFAULT_PORT = "/tmp/printer"
TIMEOUT = 30  # 等待响应的超时秒数


def open_port(port_path):
    """以非阻塞方式打开伪终端"""
    fd = os.open(port_path, os.O_RDWR | os.O_NONBLOCK)
    try:
        old = termios.tcgetattr(fd)
        # 关闭 echo，设置 raw 模式
        old[3] = old[3] & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except termios.error:
        pass
    return fd


def read_response(fd, timeout=TIMEOUT):
    """读取 Klipper 响应直到收到 ok 或超时"""
    result = []
    start = time.time()
    while time.time() - start < timeout:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            try:
                data = os.read(fd, 4096).decode("utf-8", errors="replace")
                if data:
                    result.append(data)
                    # 收到 ok 或 error 就可以返回
                    if "ok\n" in data or "!! " in data:
                        break
            except (OSError, BlockingIOError):
                pass
    return "".join(result)


def send_command(fd, cmd, wait=True):
    """发送一条 G-code 命令"""
    # 确保命令以换行结尾
    if not cmd.endswith("\n"):
        cmd += "\n"
    os.write(fd, cmd.encode())
    if wait:
        return read_response(fd)
    return ""


def parse_gcode_lines(filepath):
    """解析 G-code 文件，返回有效命令行列表"""
    lines = []
    with open(filepath, "r") as f:
        for raw in f:
            line = raw.strip()
            # 跳过空行和注释
            if not line or line.startswith(";"):
                continue
            lines.append(line)
    return lines


def run_continuous(port, gcode_file):
    """连续发送整个文件，最后输出汇总"""
    fd = open_port(port)
    lines = parse_gcode_lines(gcode_file)
    print(f"[*] 连续发送 {len(lines)} 条命令 from {gcode_file}")
    print("-" * 50)

    for i, line in enumerate(lines):
        print(f">>> {line}")
        resp = send_command(fd, line)
        if resp:
            # 只显示非 ok 的响应
            for rline in resp.strip().split("\n"):
                rline = rline.strip()
                if rline and rline != "ok":
                    print(f"    {rline}")
        time.sleep(0.05)  # 小延迟防止缓冲区溢出

    os.close(fd)
    print("-" * 50)
    print(f"[*] 完成，共 {len(lines)} 条命令")


def run_interactive(port, gcode_file):
    """逐条发送，每条命令后等待用户确认"""
    fd = open_port(port)
    lines = parse_gcode_lines(gcode_file)
    print(f"[*] 交互模式: {len(lines)} 条命令 from {gcode_file}")
    print("[*] 按 Enter 发送下一条, 's' 跳过, 'r' 查看响应, 'q' 退出")
    print("-" * 50)

    i = 0
    last_resp = ""
    while i < len(lines):
        line = lines[i]
        print(f"\n[{i+1}/{len(lines)}] >>> {line}")
        choice = input("Enter=发送, s=跳过, r=重看响应, q=退出 > ").strip().lower()

        if choice == "q":
            break
        elif choice == "s":
            i += 1
            continue
        elif choice == "r":
            print(last_resp)
            continue
        else:
            resp = send_command(fd, line)
            last_resp = resp
            if resp:
                for rline in resp.strip().split("\n"):
                    rline = rline.strip()
                    if rline:
                        print(f"    {rline}")
            i += 1

    os.close(fd)
    print("-" * 50)
    print(f"[*] 完成，已发送 {i}/{len(lines)} 条命令")


def run_single_command(port, cmd):
    """发送单条命令"""
    fd = open_port(port)
    print(f">>> {cmd}")
    resp = send_command(fd, cmd)
    if resp:
        for rline in resp.strip().split("\n"):
            rline = rline.strip()
            if rline:
                print(f"    {rline}")
    os.close(fd)


def main():
    parser = argparse.ArgumentParser(description="向 Klipper 发送 G-code")
    parser.add_argument("file", nargs="?", help="G-code 文件路径")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="交互模式，逐条发送")
    parser.add_argument("-c", "--command", help="发送单条命令")
    parser.add_argument("-p", "--port", default=DEFAULT_PORT,
                        help=f"串口路径 (默认: {DEFAULT_PORT})")
    args = parser.parse_args()

    # 检查串口是否存在
    if not os.path.exists(args.port):
        print(f"[!] 错误: 串口 {args.port} 不存在")
        print("[!] 请确认 Klipper 已启动 (python3 klippy/klippy.py printer.cfg -l /tmp/klippy.log)")
        sys.exit(1)

    if args.command:
        run_single_command(args.port, args.command)
    elif args.file:
        if args.interactive:
            run_interactive(args.port, args.file)
        else:
            run_continuous(args.port, args.file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
