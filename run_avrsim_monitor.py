#!/usr/bin/env python3
"""
Step pulse analyzer using pysimulavr.
Monitors the serial communication to count step pulses.
"""
import sys
import os
import time
import signal
import pty
import fcntl
import termios

sys.path.insert(0, '/home/alpha/simulavr/build/pysimulavr/')
import pysimulavr

SERIALBITS = 10
SIMULAVR_FREQ = 10**9

class SerialByteCounter:
    """Count and analyze bytes received from MCU."""
    def __init__(self):
        self.bytes_received = []
        self.last_print_time = time.time()

    def write_byte(self, b):
        self.bytes_received.append(b)
        # Print running count every second
        now = time.time()
        if now - self.last_print_time >= 1.0:
            print(f"  Received {len(self.bytes_received)} bytes, last: 0x{b:02x}")
            self.last_print_time = now

class SerialRxPin(pysimulavr.PySimulationMember, pysimulavr.Pin):
    """Receive serial data from MCU and pass to terminal."""
    def __init__(self, baud, terminal):
        pysimulavr.Pin.__init__(self)
        pysimulavr.PySimulationMember.__init__(self)
        self.terminal = terminal
        self.sc = pysimulavr.SystemClock.Instance()
        self.delay = SIMULAVR_FREQ // baud
        self.current = 0
        self.pos = -1

    def SetInState(self, pin):
        pysimulavr.Pin.SetInState(self, pin)
        self.state = pin.outState
        if self.pos < 0 and pin.outState == pin.LOW:
            self.pos = 0
            self.sc.Add(self)

    def DoStep(self, trueHwStep):
        ishigh = self.state == self.HIGH
        self.current |= ishigh << self.pos
        self.pos += 1
        if self.pos == 1:
            return int(self.delay * 1.5)
        if self.pos >= SERIALBITS:
            data = bytearray([(self.current >> 1) & 0xff])
            self.terminal.write(data)
            self.pos = -1
            self.current = 0
            return -1
        return self.delay

class SerialTxPin(pysimulavr.PySimulationMember, pysimulavr.Pin):
    """Send serial data to MCU."""
    def __init__(self, baud, terminal):
        pysimulavr.Pin.__init__(self)
        pysimulavr.PySimulationMember.__init__(self)
        self.terminal = terminal
        self.SetPin('H')
        self.sc = pysimulavr.SystemClock.Instance()
        self.delay = SIMULAVR_FREQ // baud
        self.current = 0
        self.pos = 0
        self.queue = bytearray()
        self.sc.Add(self)

    def DoStep(self, trueHwStep):
        if not self.pos:
            if not self.queue:
                data = self.terminal.read()
                if not data:
                    return self.delay * 100
                self.queue.extend(data)
            self.current = (self.queue.pop(0) << 1) | 0x200
        newstate = 'L'
        if self.current & (1 << self.pos):
            newstate = 'H'
        self.SetPin(newstate)
        self.pos += 1
        if self.pos >= SERIALBITS:
            self.pos = 0
        return self.delay

class TerminalIO:
    def __init__(self):
        self.fd = -1

    def run(self, fd):
        self.fd = fd

    def write(self, data):
        if self.fd >= 0:
            os.write(self.fd, data)

    def read(self):
        try:
            if self.fd >= 0:
                return os.read(self.fd, 64)
        except OSError:
            pass
        return ""

def create_pty(ptyname):
    mfd, sfd = pty.openpty()
    try:
        os.unlink(ptyname)
    except FileNotFoundError:
        pass
    os.symlink(os.ttyname(sfd), ptyname)
    fcntl.fcntl(mfd, fcntl.F_SETFL,
                fcntl.fcntl(mfd, fcntl.F_GETFL) | os.O_NONBLOCK)
    tcattr = termios.tcgetattr(mfd)
    tcattr[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP |
                    termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON)
    tcattr[1] &= ~termios.OPOST
    tcattr[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG |
                    termios.IEXTEN)
    tcattr[2] &= ~(termios.CSIZE | termios.PARENB)
    tcattr[2] |= termios.CS8
    tcattr[6][termios.VMIN] = 0
    tcattr[6][termios.VTIME] = 0
    termios.tcsetattr(mfd, termios.TCSAFLUSH, tcattr)
    return mfd

def main():
    elffile = 'out/klipper.elf'
    proc = 'atmega644'
    speed = 16000000
    baud = 250000
    ptyname = '/tmp/pseudoserial'

    # Initialize simulation
    sc = pysimulavr.SystemClock.Instance()
    dev = pysimulavr.AvrFactory.instance().makeDevice(proc)
    dev.Load(elffile)
    dev.SetClockFreq(SIMULAVR_FREQ // speed)
    sc.Add(dev)
    pysimulavr.cvar.sysConHandler.SetUseExit(False)

    # Terminal for serial communication
    io = TerminalIO()

    # Setup rx pin (MCU -> Host)
    rxpin = SerialRxPin(baud, io)
    net = pysimulavr.Net()
    net.Add(rxpin)
    net.Add(dev.GetPin("D1"))

    # Setup tx pin (Host -> MCU)
    txpin = SerialTxPin(baud, io)
    net2 = pysimulavr.Net()
    net2.Add(dev.GetPin("D0"))
    net2.Add(txpin)

    # Create terminal device
    fd = create_pty(ptyname)
    io.run(fd)

    print("Starting simulation for step pulse analysis...")
    print("Run: PYTHONPATH=klipper python3 scripts/test_klippy.py -v -d dict/dict/ test/klippy/simulavr_g1连续.test")
    print("Press Ctrl+C to stop and show analysis")
    print()

    start_time = time.time()
    byte_count = 0

    def signal_handler(sig, frame):
        elapsed = time.time() - start_time
        print(f"\n\n=== Analysis ===")
        print(f"Simulation time: {elapsed:.1f} seconds")
        print(f"Total bytes received from MCU: {byte_count}")
        print("\nNote: Step pulse analysis requires decoding the MCU command protocol.")
        print("The 'queue_step' commands contain step counts for each axis.")
        print("\nTo analyze step pulses, run:")
        print("  PYTHONPATH=klipper python3 scripts/stepstats.py <serial_log>")

        try:
            os.unlink(ptyname)
        except FileNotFoundError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        sc.RunTimeRange(0x7fff0000ffff0000)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == '__main__':
    main()