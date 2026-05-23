#!/usr/bin/env python3
"""Analyze VCD files to count step pulses."""
import sys
import re
import vcdvcd

def analyze_vcd(vcd_file, signal_name=None):
    """Analyze VCD file for signal changes."""
    print(f"Analyzing VCD file: {vcd_file}")

    # Use regex pattern for all signals
    patterns = [re.compile(".*")]
    vcd = vcdvcd.VCDVCD(vcd_file, signal_res=patterns)

    if signal_name:
        signals = [signal_name]
    else:
        signals = list(vcd.module_signals.keys())

    print(f"\nFound {len(signals)} signals")

    for sig in signals:
        try:
            vcd_signal = vcd.module_signals[sig]
            print(f"\n=== Signal: {sig} ===")

            # Get all changes for this signal
            changes = list(vcd.signal_changes[sig])
            print(f"Total changes: {len(changes)}")

            if len(changes) > 0:
                # Count transitions
                transitions = {}
                for i, (time, val) in enumerate(changes):
                    if val not in transitions:
                        transitions[val] = 0
                    transitions[val] += 1

                print(f"Value distribution: {transitions}")

                # Calculate time between changes
                if len(changes) > 1:
                    intervals = []
                    for i in range(1, len(changes)):
                        interval = changes[i][0] - changes[i-1][0]
                        intervals.append(interval)

                    print(f"Time intervals (ns):")
                    print(f"  Min: {min(intervals)}")
                    print(f"  Max: {max(intervals)}")
                    print(f"  Avg: {sum(intervals)/len(intervals):.2f}")

                    # Count step pulses (transitions from high to low or low to high)
                    # A step pulse typically goes: high->low->high or low->high->low
                    step_pulses = 0
                    for i in range(len(changes) - 2):
                        v1, v2, v3 = changes[i][1], changes[i+1][1], changes[i+2][1]
                        if v1 != v2 and v2 != v3:
                            step_pulses += 1
                    print(f"  Estimated step pulses: {step_pulses}")
            else:
                print("  No changes detected!")

        except KeyError as e:
            print(f"  Signal '{sig}' not found in VCD file")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_vcd.py <vcd_file> [signal_name]")
        print("Example: python3 analyze_vcd.py step_pulses.vcd PORTA.A5-Out")
        sys.exit(1)

    vcd_file = sys.argv[1]
    signal_name = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        analyze_vcd(vcd_file, signal_name)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()