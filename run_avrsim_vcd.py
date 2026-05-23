#!/usr/bin/env python3
"""
Custom Simulavr runner with VCD trace for step pulse capture.
"""
import sys, os, time, pty, fcntl, termios, errno, signal
sys.path.insert(0, '/home/alpha/simulavr/build/pysimulavr/')
import pysimulavr

SERIALBITS = 10
SIMULAVR_FREQ = 10**9

class SerialRxPin(pysimulavr.PySimulationMember, pysimulavr.Pin):
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
        except os.error as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                pass
        return ""

def create_pty(ptyname):
    mfd, sfd = pty.openpty()
    try:
        os.unlink(ptyname)
    except os.error:
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
    tracefile = 'step_pulses.vcd'

    # Initialize simulation
    sc = pysimulavr.SystemClock.Instance()
    dman = pysimulavr.DumpManager.Instance()
    dman.SetSingleDeviceApp()

    dev = pysimulavr.AvrFactory.instance().makeDevice(proc)
    dev.Load(elffile)
    dev.SetClockFreq(SIMULAVR_FREQ // speed)
    sc.Add(dev)
    pysimulavr.cvar.sysConHandler.SetUseExit(False)

    # Setup VCD tracing
    sigs = '+ PORTA.A5-Out\n+ PORTA.A4-Out\n+ PORTA.A1-Out'
    dman.addDumpVCD(tracefile, sigs, "ns", False, False)

    # Setup terminal
    io = TerminalIO()

    # Setup rx pin
    rxpin = SerialRxPin(baud, io)
    net = pysimulavr.Net()
    net.Add(rxpin)
    net.Add(dev.GetPin("D1"))

    # Setup tx pin
    txpin = SerialTxPin(baud, io)
    net2 = pysimulavr.Net()
    net2.Add(dev.GetPin("D0"))
    net2.Add(txpin)

    print("Starting AVR simulation with VCD tracing")
    print(f"Machine: {proc} @ {speed}Hz")
    print(f"Serial: {ptyname} @ {baud} baud")
    print(f"Trace: {tracefile}")

    # Create terminal device
    fd = create_pty(ptyname)

    io.run(fd)
    dman.start()

    def cleanup():
        print("Stopping simulation...")
        # Force cycle to flush VCD buffers
        dman.cycle()
        dman.stopApplication()
        try:
            os.unlink(ptyname)
        except:
            pass
        print(f"VCD saved to {tracefile}")

    signal.signal(signal.SIGINT, lambda s,f: cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s,f: cleanup() or sys.exit(0))

    try:
        sc.RunTimeRange(0x7fff0000ffff0000)
    finally:
        cleanup()

if __name__ == '__main__':
    main()