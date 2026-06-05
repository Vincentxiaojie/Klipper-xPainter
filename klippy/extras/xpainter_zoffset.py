# xPainter calibration module
#
# Provides XP_* commands for tool_length, pivot_y, and Z offset
# calibration workflows with machine-assisted alignment.
#
# Copyright (C) 2026  xPainter
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import math, logging


class XPainterCalibration:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.z_offset = config.getfloat('z_offset', 0.)

        # Read printer section parameters
        pconfig = config.getsection('printer')
        self._tool_length = pconfig.getfloat('tool_length', 0.)
        self._pivot_y = pconfig.getfloat('pivot_y', 0.)

        # G-code dispatcher
        self.gcode = self.printer.lookup_object('gcode')

        # Register commands
        self._register_commands()

        # State tracking for POINT macros (call counting)
        self._point_state = {}  # key -> {'x1','y1','angle','count'}

        # Auto-restore Z offset on ready
        self.printer.register_event_handler('klippy:ready', self._handle_ready)

    def _register_commands(self):
        # Z offset
        self.gcode.register_command(
            'XP_Z_CAL', self.cmd_XP_Z_CAL,
            desc='Start Z zero calibration (paper surface)')
        self.gcode.register_command(
            'XP_Z_TOUCH', self.cmd_XP_Z_TOUCH,
            desc='Confirm paper touch and set Z=0')
        self.gcode.register_command(
            'XP_RESTORE_Z', self.cmd_XP_RESTORE_Z,
            desc='Restore Z zero after homing (called by G28)')
        self.gcode.register_command(
            'XP_CLEAR_Z_OFFSET', self.cmd_XP_CLEAR_Z_OFFSET,
            desc='Clear Z offset to zero')

        # Tool length calibration
        self.gcode.register_command(
            'XP_TOOL_CAL', self.cmd_XP_TOOL_CAL,
            desc='Start tool_length calibration')
        self.gcode.register_command(
            'XP_TOOL_TOUCH', self.cmd_XP_TOOL_TOUCH,
            desc='Touch paper and mark calibration dots')
        self.gcode.register_command(
            'XP_TOOL_POINT', self.cmd_XP_TOOL_POINT,
            desc='Record aligned position for tool calibration')
        self.gcode.register_command(
            'XP_TOOL_APPLY', self.cmd_XP_TOOL_APPLY,
            desc='Calculate and apply new tool_length')

        # Pivot calibration
        self.gcode.register_command(
            'XP_PIVOT_CAL', self.cmd_XP_PIVOT_CAL,
            desc='Start pivot_y calibration')
        self.gcode.register_command(
            'XP_PIVOT_TOUCH', self.cmd_XP_PIVOT_TOUCH,
            desc='Touch paper and mark pivot calibration dots')
        self.gcode.register_command(
            'XP_PIVOT_POINT', self.cmd_XP_PIVOT_POINT,
            desc='Record aligned position for pivot calibration')
        self.gcode.register_command(
            'XP_PIVOT_APPLY', self.cmd_XP_PIVOT_APPLY,
            desc='Calculate and apply new pivot_y')

        # Change tool workflow
        self.gcode.register_command(
            'XP_CHANGE_TOOL', self.cmd_XP_CHANGE_TOOL,
            desc='Start tool change workflow')
        self.gcode.register_command(
            'XP_TOOL_READY', self.cmd_XP_TOOL_READY,
            desc='Confirm tool installed, begin calibration')

    # ============================================================
    # Helpers
    # ============================================================

    def _respond(self, gcmd, msg):
        """Unified response wrapper."""
        prefix = "[XP] "
        gcmd.respond_info(prefix + msg)

    def _run_gcode(self, script):
        """Execute a G-code script block. Includes G4 delays where needed."""
        self.gcode.run_script_from_command(script)

    def _get_toolhead(self):
        return self.printer.lookup_object('toolhead')

    def _get_configfile(self):
        return self.printer.lookup_object('configfile')

    def _get_current_xy(self):
        """Get current X,Y in gcode (tip) coordinate space."""
        gcode_move = self.printer.lookup_object('gcode_move')
        pos = gcode_move.get_status()['gcode_position']
        return pos[0], pos[1]

    def _get_current_z(self):
        """Get current Z in gcode (tip) coordinate space.

        Must use gcode position (not toolhead pivot position) because
        XP_RESTORE_Z issues G1 Z{value} — a gcode-space command.
        toolhead.get_position() returns pivot coordinates, which differ
        by tool_length, causing a Z offset error after restore.
        """
        gcode_move = self.printer.lookup_object('gcode_move')
        return gcode_move.get_status()['gcode_position'][2]

    # ============================================================
    # Z Offset commands
    # ============================================================

    def _handle_ready(self):
        """Auto-restore Z offset on startup after homing is complete."""
        # The actual restore happens in XP_RESTORE_Z, called by G28 macro
        pass

    def _get_position_endstop_z(self):
        """Read Z position_endstop from stepper config."""
        try:
            cf = self._get_configfile()
            if cf.fileconfig.has_option('stepper_z', 'position_endstop'):
                return cf.fileconfig.getfloat('stepper_z', 'position_endstop')
        except Exception:
            pass
        return 0.0

    cmd_XP_Z_CAL_help = "Start Z zero calibration"

    def cmd_XP_Z_CAL(self, gcmd):
        self._respond(gcmd, "=== Z 零点标定 ===")
        self._respond(gcmd, "请手动下探触纸，笔尖刚好接触纸面")
        self._respond(gcmd, "确认触纸后执行 XP_Z_TOUCH")

    cmd_XP_Z_TOUCH_help = "Set current Z position as Z=0"

    def cmd_XP_Z_TOUCH(self, gcmd):
        # Record machine Z coordinate of paper surface
        z_paper = self._get_current_z()
        # Apply Z=0 at current position via G92
        self._run_gcode('G92 Z0')
        # Persist to config section
        cf = self._get_configfile()
        cf.set(self.name, 'z_offset', '%.3f' % z_paper)
        self.z_offset = z_paper
        self._respond(gcmd, "Z 零点已标定，纸面=Z0 (machine Z=%.3f)" % z_paper)
        self._respond(gcmd, "执行 SAVE_CONFIG 持久化到 printer.cfg")

    cmd_XP_RESTORE_Z_help = "Restore Z zero after G28 Z homing"

    def cmd_XP_RESTORE_Z(self, gcmd):
        """Restore Z zero after G28 Z completes. Called by G28 macro."""
        if self.z_offset == 0.:
            self._respond(gcmd, "Z 零点未标定，请执行 XP_Z_CAL → XP_Z_TOUCH")
            return
        # Move to paper surface Z then set Z=0
        self._run_gcode('G1 Z%.3f F600' % self.z_offset)
        self._run_gcode('G92 Z0')

    cmd_XP_CLEAR_Z_OFFSET_help = "Clear Z offset to zero"

    def cmd_XP_CLEAR_Z_OFFSET(self, gcmd):
        # Reset: Z zero = endstop position
        z_endstop = self._get_position_endstop_z()
        cf = self._get_configfile()
        cf.set(self.name, 'z_offset', '0.0')
        self.z_offset = 0.0
        self._run_gcode('SET_GCODE_OFFSET Z=0')
        self._respond(gcmd, "Z offset 已清零，请重新标定 Z 零点")

    # ============================================================
    # Tool Length calibration commands
    # ============================================================

    cmd_XP_TOOL_CAL_help = "Start tool_length calibration"

    def cmd_XP_TOOL_CAL(self, gcmd):
        # Reset point state
        self._point_state['tool'] = {'x1': 0., 'y1': 0., 'count': 0}
        self._respond(gcmd, "=== Tool Length 标定 (机器辅助) ===")
        # Home all axes, move to center
        self._run_gcode('G28')
        self._run_gcode('G1 X100 Y100 Z30 F3000')
        self._run_gcode('G1 B0 F400')
        self._respond(gcmd, "请下探触纸后执行 XP_TOOL_TOUCH")

    cmd_XP_TOOL_TOUCH_help = "Touch paper, mark B=0 and B=30 dots"

    def cmd_XP_TOOL_TOUCH(self, gcmd):
        self._respond(gcmd, "触纸确认，开始打点...")
        # Set Z=0 at touch point
        self._run_gcode('G92 Z0')
        # Dot 1: B=0 (reference)
        self._run_gcode('PEN_DOWN\nG4 P500\nPEN_UP')
        self._respond(gcmd, "打点1: B=0 (参考点) 已完成")
        # Dot 2: B=30
        self._run_gcode('G91\nG1 Z20 F200\nG90')
        self._run_gcode('G1 B30 F400')
        self._run_gcode('G1 Z0 F200')
        self._run_gcode('PEN_DOWN\nG4 P500\nPEN_UP')
        self._respond(gcmd, "打点2: B=30 已完成")
        # Return to safe position
        self._run_gcode('G91\nG1 Z20 F200\nG90')
        self._run_gcode('G1 B0 F400')
        self._respond(gcmd, "请手动 jog 笔尖对准点1 (B=0打的点)")
        self._respond(gcmd, "对准后执行 XP_TOOL_POINT")

    cmd_XP_TOOL_POINT_help = "Record aligned position for tool calibration"

    def cmd_XP_TOOL_POINT(self, gcmd):
        state = self._point_state.setdefault('tool', {'count': 0})
        x, y = self._get_current_xy()
        count = state['count']
        if count == 0:
            # First call: record point 1
            state['x1'] = x
            state['y1'] = y
            state['count'] = 1
            self._respond(gcmd, "点1 已记录 (%.3f, %.3f)" % (x, y))
            self._respond(gcmd, "请 jog 笔尖对准点2 (B=30打的点)")
            self._respond(gcmd, "对准后再次执行 XP_TOOL_POINT")
        else:
            # Second call: record point 2 and calculate
            x1, y1 = state['x1'], state['y1']
            dx = x - x1
            dy = y - y1
            # Calculate tool_length correction
            B_angle = 30.0
            sin_b = math.sin(math.radians(B_angle))
            if abs(sin_b) < 1e-10:
                raise gcmd.error("B角度不能为0")
            delta_l = dx / sin_b
            L_current = self._read_tool_length()
            L_new = L_current + delta_l

            self._respond(gcmd, "点2 已记录 (%.3f, %.3f)" % (x, y))
            self._respond(gcmd, "------------------------------")
            self._respond(gcmd, "Δx = %.3f mm  Δy = %.3f mm" % (dx, dy))
            self._respond(gcmd, "ΔL = %.3f mm (Δx / sin(30°))" % delta_l)
            self._respond(gcmd, "当前 tool_length = %.3f mm" % L_current)
            self._respond(gcmd, "推荐 tool_length = %.3f mm" % L_new)
            self._respond(gcmd, "------------------------------")
            self._respond(gcmd, "确认应用? 执行 XP_TOOL_APPLY")
            # Save for APPLY
            state['L_new'] = L_new
            state['count'] = 2

    cmd_XP_TOOL_APPLY_help = "Apply calculated tool_length"

    def cmd_XP_TOOL_APPLY(self, gcmd):
        state = self._point_state.get('tool', {})
        L_new = state.get('L_new')
        if L_new is None:
            self._respond(gcmd, "错误: 请先完成 XP_TOOL_CAL + XP_TOOL_POINT 流程")
            return
        L_current = self._read_tool_length()
        # Clear Z offset first (safety!) — reset z_paper to 0 (endstop)
        cf = self._get_configfile()
        cf.set(self.name, 'z_offset', '0.0')
        self.z_offset = 0.0
        self._run_gcode('SET_GCODE_OFFSET Z=0')
        self._respond(gcmd, "Z offset 已自动清零 (安全保护)")

        # Update tool_length in printer section
        cf.set('printer', 'tool_length', '%.3f' % L_new)
        self._tool_length = L_new
        self._respond(gcmd, "tool_length: %.3f → %.3f" % (L_current, L_new))
        self._respond(gcmd, "请执行 SAVE_CONFIG 持久化，然后重启 Klipper")
        self._respond(gcmd, "重启后请执行 XP_Z_CAL 重新标定纸面零点")
        # Reset state
        self._point_state.pop('tool', None)

    # ============================================================
    # Pivot Y calibration commands
    # ============================================================

    cmd_XP_PIVOT_CAL_help = "Start pivot_y calibration"

    def cmd_XP_PIVOT_CAL(self, gcmd):
        self._point_state['pivot'] = {'x1': 0., 'y1': 0., 'count': 0}
        self._respond(gcmd, "=== Pivot Y 标定 (机器辅助) ===")
        self._run_gcode('G28')
        self._run_gcode('G1 X100 Y100 Z30 F3000')
        self._run_gcode('G1 B0 C0 F400')
        self._respond(gcmd, "请下探触纸后执行 XP_PIVOT_TOUCH")

    cmd_XP_PIVOT_TOUCH_help = "Touch paper, mark C=0 and C=30 dots"

    def cmd_XP_PIVOT_TOUCH(self, gcmd):
        self._respond(gcmd, "触纸确认，开始打点...")
        self._run_gcode('G92 Z0')
        # Dot 1: C=0 (reference)
        self._run_gcode('PEN_DOWN\nG4 P500\nPEN_UP')
        self._respond(gcmd, "打点1: C=0 (参考点) 已完成")
        # Dot 2: C=30
        self._run_gcode('G91\nG1 Z20 F200\nG90')
        self._run_gcode('G1 C30 F400')
        self._run_gcode('G1 Z0 F200')
        self._run_gcode('PEN_DOWN\nG4 P500\nPEN_UP')
        self._respond(gcmd, "打点2: C=30 已完成")
        # Return to safe position
        self._run_gcode('G91\nG1 Z20 F200\nG90')
        self._run_gcode('G1 C0 F400')
        self._respond(gcmd, "请手动 jog 笔尖对准点1 (C=0打的点)")
        self._respond(gcmd, "对准后执行 XP_PIVOT_POINT")

    cmd_XP_PIVOT_POINT_help = "Record aligned position for pivot calibration"

    def cmd_XP_PIVOT_POINT(self, gcmd):
        state = self._point_state.setdefault('pivot', {'count': 0})
        x, y = self._get_current_xy()
        count = state['count']
        if count == 0:
            state['x1'] = x
            state['y1'] = y
            state['count'] = 1
            self._respond(gcmd, "点1 已记录 (%.3f, %.3f)" % (x, y))
            self._respond(gcmd, "请 jog 笔尖对准点2 (C=30打的点)")
            self._respond(gcmd, "对准后再次执行 XP_PIVOT_POINT")
        else:
            x1, y1 = state['x1'], state['y1']
            dx = x - x1
            dy = y - y1
            C_angle = 30.0
            sin_c = math.sin(math.radians(C_angle))
            if abs(sin_c) < 1e-10:
                raise gcmd.error("C角度不能为0")
            offset = -dx / sin_c
            pivot_current = self._read_pivot_y()

            self._respond(gcmd, "点2 已记录 (%.3f, %.3f)" % (x, y))
            self._respond(gcmd, "------------------------------")
            self._respond(gcmd, "Δx = %.3f mm  Δy = %.3f mm" % (dx, dy))
            self._respond(gcmd, "offset = %.3f mm (-Δx / sin(30°))" % offset)
            self._respond(gcmd, "当前 pivot_y = %.3f mm" % pivot_current)
            self._respond(gcmd, "推荐 pivot_y = %.3f mm" % offset)
            self._respond(gcmd, "------------------------------")
            self._respond(gcmd, "确认应用? 执行 XP_PIVOT_APPLY")
            state['pivot_new'] = offset
            state['count'] = 2

    cmd_XP_PIVOT_APPLY_help = "Apply calculated pivot_y"

    def cmd_XP_PIVOT_APPLY(self, gcmd):
        state = self._point_state.get('pivot', {})
        pivot_new = state.get('pivot_new')
        if pivot_new is None:
            self._respond(gcmd, "错误: 请先完成 XP_PIVOT_CAL + XP_PIVOT_POINT 流程")
            return
        pivot_current = self._read_pivot_y()
        cf = self._get_configfile()
        cf.set('printer', 'pivot_y', '%.3f' % pivot_new)
        self._pivot_y = pivot_new
        self._respond(gcmd, "pivot_y: %.3f → %.3f" % (pivot_current, pivot_new))
        self._respond(gcmd, "请执行 SAVE_CONFIG 持久化，然后重启 Klipper")
        self._point_state.pop('pivot', None)

    # ============================================================
    # Change Tool workflow
    # ============================================================

    cmd_XP_CHANGE_TOOL_help = "Start tool change workflow"

    def cmd_XP_CHANGE_TOOL(self, gcmd):
        self._respond(gcmd, "=== 换笔工作流 ===")
        # Lift to safe Z
        self._run_gcode('G91\nG1 Z30 F600\nG90')
        # Home B and C
        # Determine homed status
        toolhead = self._get_toolhead()
        homed = toolhead.get_status(None)['homed_axes']
        if 'b' not in homed or 'c' not in homed:
            self._run_gcode('G28 B C')
        self._run_gcode('G1 B0 C0 F400')
        self._respond(gcmd, "请更换笔头")
        self._respond(gcmd, "完成后执行 XP_TOOL_READY")

    cmd_XP_TOOL_READY_help = "Confirm tool installed, begin calibration"

    def cmd_XP_TOOL_READY(self, gcmd):
        self._respond(gcmd, "新笔已就绪，开始 tool_length 标定...")
        # Reset point state and launch tool calibration
        self._point_state['tool'] = {'x1': 0., 'y1': 0., 'count': 0}
        self.cmd_XP_TOOL_CAL(gcmd)

    # ============================================================
    # Config reading helpers
    # ============================================================

    def _read_tool_length(self):
        """Read current tool_length from printer config."""
        try:
            cf = self._get_configfile()
            if cf.fileconfig.has_option('printer', 'tool_length'):
                return cf.fileconfig.getfloat('printer', 'tool_length')
        except Exception:
            pass
        return self._tool_length

    def _read_pivot_y(self):
        """Read current pivot_y from printer config."""
        try:
            cf = self._get_configfile()
            if cf.fileconfig.has_option('printer', 'pivot_y'):
                return cf.fileconfig.getfloat('printer', 'pivot_y')
        except Exception:
            pass
        return self._pivot_y

    def get_status(self, eventtime):
        return {
            'z_offset': self.z_offset,
            'tool_length': self._read_tool_length(),
            'pivot_y': self._read_pivot_y(),
        }


def load_config(config):
    return XPainterCalibration(config)
