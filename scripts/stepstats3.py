#!/usr/bin/env python3
# Analyze stepper pulse counts from Klipper test output
import sys

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 stepstats3.py <output_file>")
        sys.exit(1)

    filename = sys.argv[1]

    steppers = {}
    with open(filename, 'rb') as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            args = dict([p.split(b'=', 1) for p in parts[1:]])
            if parts[0] == b'config_stepper':
                oid = int(args[b'oid'])
                steppers[oid] = {'dir_cmds': 0, 'dir': 0, 'queue_cmds': 0, 'neg_steps': 0, 'pos_steps': 0}
            elif parts[0] == b'set_next_step_dir':
                oid = int(args[b'oid'])
                if oid in steppers:
                    steppers[oid]['dir_cmds'] += 1
                    steppers[oid]['dir'] = int(args[b'dir'])
            elif parts[0] == b'queue_step':
                oid = int(args[b'oid'])
                if oid in steppers:
                    steppers[oid]['queue_cmds'] += 1
                    count = int(args[b'count'])
                    direction = steppers[oid]['dir']
                    if direction == 0:
                        steppers[oid]['neg_steps'] += count
                    else:
                        steppers[oid]['pos_steps'] += count

    print(f"{'OID':<6} {'Dir Cmds':<10} {'Queue Cmds':<12} {'Neg Steps':<12} {'Pos Steps':<12} {'Net':<10}")
    print("-" * 70)
    for oid in sorted(steppers.keys()):
        s = steppers[oid]
        net = s['pos_steps'] - s['neg_steps']
        print(f"{oid:<6} {s['dir_cmds']:<10} {s['queue_cmds']:<12} {s['neg_steps']:<12} {s['pos_steps']:<12} {net:<10}")

if __name__ == '__main__':
    main()