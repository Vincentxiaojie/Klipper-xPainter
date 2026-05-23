#!/usr/bin/env python3
"""Parse Klipper binary output and count queue_step commands by OID"""
import struct
import sys

def main():
    filename = '_test_output'
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"File {filename} not found")
        return

    step_counts = {}
    pos = 0
    while pos < len(data) - 8:
        # Try to read as uint32 prefix
        prefix = data[pos:pos+4]
        if len(prefix) < 4:
            break
        # Look for config_stepper, set_next_step_dir, queue_step markers
        if data[pos:pos+4] == b'\x00\x00\x00\x00':
            pos += 1
            continue

        # Try parsing queue_step manually
        # queue_step format: variable length, typically has oid= and count= fields
        line_end = data.find(b'\n', pos)
        if line_end == -1:
            line_end = len(data)
        line = data[pos:line_end]
        if b'queue_step' in line:
            # Parse oid and count
            oid = None
            count = None
            parts = line.split()
            for part in parts:
                if part.startswith(b'oid='):
                    oid = int(part[4:])
                elif part.startswith(b'count='):
                    count = int(part[6:])
            if oid is not None and count is not None:
                step_counts[oid] = step_counts.get(oid, 0) + count
        pos = line_end + 1

    print(f"{'OID':<8} {'Total Steps':<15}")
    print("-" * 25)
    for oid in sorted(step_counts.keys()):
        print(f"{oid:<8} {step_counts[oid]:<15}")

if __name__ == '__main__':
    main()