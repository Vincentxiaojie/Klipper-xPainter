#!/usr/bin/env python3
"""Run test and capture serial output for step pulse analysis."""
import sys
import os
import time
import subprocess

def run_test_with_serial_capture(test_file, output_file):
    """Run a klippy test while capturing serial communication."""

    # Start avrsim in background, capturing serial to file
    avrsim_cmd = [
        sys.executable, './scripts/avrsim.py', 'out/klipper.elf'
    ]

    print(f"Starting avrsim...")
    avrsim_proc = subprocess.Popen(
        avrsim_cmd,
        stdout=open('/tmp/avrsim_capture.log', 'w'),
        stderr=subprocess.STDOUT,
        cwd='/home/alpha/xpainter/klipper'
    )

    time.sleep(2)  # Wait for avrsim to start

    # Run klippy test
    test_cmd = [
        sys.executable, 'scripts/test_klippy.py',
        '-v', '-d', 'dict/dict/', test_file
    ]

    print(f"Running test: {test_file}")
    test_result = subprocess.run(
        test_cmd,
        capture_output=True,
        text=True,
        cwd='/home/alpha/xpainter/klipper',
        env={**os.environ, 'PYTHONPATH': 'klipper'}
    )

    print(f"Test output:\n{test_result.stdout}")
    if test_result.stderr:
        print(f"Test errors:\n{test_result.stderr}")

    # Stop avrsim
    print("Stopping avrsim...")
    avrsim_proc.terminate()
    avrsim_proc.wait(timeout=5)

    # Save serial output
    with open('/tmp/avrsim_capture.log', 'r') as f:
        content = f.read()

    # Extract only the serial communication lines
    serial_lines = []
    in_serial = False
    for line in content.split('\n'):
        # Skip WARNING lines
        if 'WARNING:' in line:
            continue
        # This is serial output from avrsim
        if 'Serial:' in line or in_serial:
            in_serial = True
            serial_lines.append(line)

    with open(output_file, 'w') as f:
        f.write('\n'.join(serial_lines))

    print(f"\nSerial output saved to: {output_file}")
    print(f"File size: {os.path.getsize(output_file)} bytes")

    return test_result.returncode == 0

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 capture_serial.py <test_file> <output_file>")
        sys.exit(1)

    test_file = sys.argv[1]
    output_file = sys.argv[2]

    success = run_test_with_serial_capture(test_file, output_file)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()