#!/usr/bin/env python3
"""Simple step counter - just count queue_step commands by OID"""
import re
import sys

if len(sys.argv) != 2:
    print("Usage: python3 count_steps.py <output_file>")
    sys.exit(1)

filename = sys.argv[1]
step_counts = {}

with open(filename, 'rb') as f:
    for line in f:
        try:
            line = line.decode('utf-8', errors='replace')
        except:
            continue
        if line.startswith('queue_step'):
            # Extract oid and count
            oid_match = re.search(r'oid=(\d+)', line)
            count_match = re.search(r'count=(\d+)', line)
            if oid_match and count_match:
                oid = int(oid_match.group(1))
                count = int(count_match.group(1))
                step_counts[oid] = step_counts.get(oid, 0) + count

print(f"{'OID':<8} {'Total Steps':<15}")
print("-" * 25)
for oid in sorted(step_counts.keys()):
    print(f"{oid:<8} {step_counts[oid]:<15}")

print()
print("XYZ steppers (X=2, Y=5, Z=8):")
for oid in [2, 5, 8]:
    print(f"  oid={oid}: {step_counts.get(oid, 0)} steps")

print()
print("ABC steppers (A=11, B=14, C=17):")
for oid in [11, 14, 17]:
    print(f"  oid={oid}: {step_counts.get(oid, 0)} steps")