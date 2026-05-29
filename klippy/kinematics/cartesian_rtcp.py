# Code for handling multi-axis kinematics with RTCP (Rotation Tool Center Point)
#
# Based on cartesian_abc.py. Supports X, Y, Z + 2 rotary axes + E.
# RTCP: when rotary axes tilt the tool, XYZ automatically compensates
# to keep the tool tip at the programmed position.
#
# rotary_config: 'bc' (default) — B around Y, C around Z (head-head with twist)
#                'ab'         — A around X, B around Y (standard tilting head)
#
import logging, math
import stepper

class CartesianRTCPKinematics:
    def __init__(self, toolhead, config):
        self.printer = config.get_printer()
        self.tool_length = config.getfloat('tool_length', 0., above=0.)
        self.rotary_config = config.get('rotary_config', 'bc').lower()
        if self.rotary_config not in ('ab', 'bc'):
            raise config.error("rotary_config must be 'ab' or 'bc'")
        # Determine which axes are configured
        self.axes = 'xyz'
        for axis in 'abc':
            if config.has_section('stepper_' + axis):
                self.axes += axis
        # Setup axis rails
        self.rails = [stepper.LookupMultiRail(config.getsection('stepper_' + n))
                      for n in self.axes]
        for rail, axis in zip(self.rails, self.axes):
            rail.setup_itersolve('cartesian_stepper_alloc', axis.encode())
        ranges = [r.get_range() for r in self.rails]
        self.axes_min = toolhead.Coord([r[0] for r in ranges] + [0.] * (6 - len(ranges)))
        self.axes_max = toolhead.Coord([r[1] for r in ranges] + [0.] * (6 - len(ranges)))
        for s in self.get_steppers():
            s.set_trapq(toolhead.get_trapq())
        # Setup boundary checks
        max_velocity, max_accel = toolhead.get_max_velocity()
        self.max_z_velocity = config.getfloat('max_z_velocity', max_velocity,
                                              above=0., maxval=max_velocity)
        self.max_z_accel = config.getfloat('max_z_accel', max_accel,
                                           above=0., maxval=max_accel)
        self.limits = [(1.0, -1.0)] * len(self.axes)
        # Map rail index to commanded_pos index (E is at commanded_pos[3])
        self._pos_idx = []
        for axis_name in self.axes:
            if axis_name in 'xyz':
                self._pos_idx.append('xyz'.index(axis_name))
            else:
                self._pos_idx.append(4 + 'abc'.index(axis_name))
        # Per-axis endstop offsets (read from each stepper config)
        self._endstop_offsets = {}
        for axis_name in self.axes:
            sconfig = config.getsection('stepper_' + axis_name)
            offset = sconfig.getfloat('homing_endstop_offset', 0.)
            self._endstop_offsets[axis_name] = offset
        # Register as gcode_move transform for position display (pivot -> tip)
        self.next_transform = None
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def get_steppers(self):
        return [s for rail in self.rails for s in rail.get_steppers()]

    def calc_position(self, stepper_positions):
        # Stepper positions are in pivot space. Convert to tip for reporting.
        pos = [stepper_positions[rail.get_name()] for rail in self.rails]
        # Pad to 7 elements [X, Y, Z, E, A, B, C]
        while len(pos) < 7:
            pos.append(0.)
        self._apply_inverse_rtcp(pos)
        return pos

    def update_limits(self, i, range):
        l, h = self.limits[i]
        if l <= h:
            self.limits[i] = range

    def set_position(self, newpos, homing_axes):
        # newpos is in PIVOT space (already transformed by toolhead hook)
        toolhead = self.printer.lookup_object('toolhead')
        while len(toolhead.commanded_pos) < len(newpos):
            toolhead.commanded_pos.append(0.0)
        # Build rail-coordinate position array: [X, Y, Z, A, B, C]
        # Axis letter → rail coordinate index in C itersolve_set_position
        RAIL_IDX = {'x': 0, 'y': 1, 'z': 2, 'a': 3, 'b': 4, 'c': 5}
        rail_pos = [0.] * 6
        for i, rail in enumerate(self.rails):
            pos_idx = self._pos_idx[i]
            if pos_idx < len(newpos):
                rail_pos[RAIL_IDX[self.axes[i]]] = newpos[pos_idx]
        for i, rail in enumerate(self.rails):
            rail.set_position(rail_pos)
        for axis_name in homing_axes:
            axis = self.axes.index(axis_name)
            rail = self.rails[axis]
            self.limits[axis] = rail.get_range()

    def clear_homing_state(self, clear_axes):
        for axis, axis_name in enumerate(self.axes):
            if axis_name in clear_axes:
                self.limits[axis] = (1.0, -1.0)

    def home_axis(self, homing_state, axis, rail):
        # Homing works in pivot space — no RTCP transform needed
        pos_idx = self._pos_idx[axis]
        position_min, position_max = rail.get_range()
        hi = rail.get_homing_info()
        homepos = [None] * 7
        homepos[pos_idx] = hi.position_endstop
        # Determine primary direction from commanded position.
        # For rotary axes with endstop in the middle of range,
        # this auto-selects the direction that points toward the endstop.
        # For linear axes (endstop at range limit), this matches static config.
        curpos = rail.get_commanded_position()
        if curpos > hi.position_endstop:
            first_dir = False  # home negative (toward endstop)
        elif curpos < hi.position_endstop:
            first_dir = True   # home positive (toward endstop)
        else:
            first_dir = hi.positive_dir  # at endstop, use config default
        # Two attempts: primary direction (1.5x), then opposite (2.5x).
        # The larger multiplier on retry guarantees endstop coverage even
        # if the first attempt pushed the axis the wrong way (e.g. after
        # FORCE_MOVE when commanded position doesn't match physical).
        second_dir = not first_dir
        attempts = [(first_dir, 1.5), (second_dir, 2.5)]
        last_error = None
        for effective_dir, multiplier in attempts:
            forcepos = list(homepos)
            forcepos[pos_idx] = homepos[pos_idx]
            if effective_dir:
                forcepos[pos_idx] -= multiplier * (hi.position_endstop - position_min)
            else:
                forcepos[pos_idx] += multiplier * (position_max - hi.position_endstop)
            tried_manual_retract = False
            while True:
                try:
                    homing_state.home_rails([rail], forcepos, homepos)
                    # Apply endstop offset: physically move from trigger
                    # point to true zero, then set coordinate.
                    offset = self._endstop_offsets.get(self.axes[axis], 0.)
                    if offset != 0.:
                        toolhead = self.printer.lookup_object('toolhead')
                        # Temporarily disable RTCP so the post-homing
                        # jog moves only the target rotary axis.
                        saved_L = self.tool_length
                        self.tool_length = 0.
                        try:
                            pos = list(toolhead.get_position())
                            if effective_dir:
                                pos[pos_idx] += offset
                            else:
                                pos[pos_idx] -= offset
                            toolhead.move(pos, hi.speed)
                            toolhead.wait_moves()
                        finally:
                            self.tool_length = saved_L
                        th_pos = list(toolhead.get_position())
                        th_pos[pos_idx] = hi.position_endstop
                        toolhead.set_position(th_pos)
                    return
                except self.printer.command_error as e:
                    if not tried_manual_retract and "still triggered" in str(e):
                        tried_manual_retract = True
                        toolhead = self.printer.lookup_object('toolhead')
                        # Disable RTCP so the retract jog only
                        # moves the target rotary axis.
                        saved_L = self.tool_length
                        self.tool_length = 0.
                        try:
                            pos = list(toolhead.get_position())
                            manual_retract = hi.retract_dist * 3
                            if effective_dir:
                                pos[pos_idx] -= manual_retract
                            else:
                                pos[pos_idx] += manual_retract
                            pos[pos_idx] = max(position_min,
                                               min(position_max, pos[pos_idx]))
                            toolhead.move(pos, hi.retract_speed)
                            toolhead.wait_moves()
                        finally:
                            self.tool_length = saved_L
                        continue
                    last_error = e
                    break
        raise last_error

    def home(self, homing_state):
        for axis in homing_state.get_axes():
            # axis is a commanded_pos index; convert to rail index via _pos_idx
            if axis in self._pos_idx:
                rail_idx = self._pos_idx.index(axis)
                self.home_axis(homing_state, rail_idx, self.rails[rail_idx])

    def _check_endstops(self, move):
        end_pos = move.end_pos
        for i in range(len(self.axes)):
            pos_idx = self._pos_idx[i]
            if pos_idx >= len(move.axes_d):
                break
            if (move.axes_d[pos_idx]
                and (end_pos[pos_idx] < self.limits[i][0]
                     or end_pos[pos_idx] > self.limits[i][1])):
                if self.limits[i][0] > self.limits[i][1]:
                    if i >= 3:
                        continue
                    raise move.move_error("Must home axis first")
                raise move.move_error()

    def _adjust_move_d_for_rotary(self, move):
        L = self.tool_length
        if not L:
            return False
        # Determine rotary axis indices based on config
        if self.rotary_config == 'bc':
            rotary_idx = [5, 6]  # B, C in commanded_pos
        else:
            rotary_idx = [4, 5]  # A, B in commanded_pos
        # Recover tip-space coordinates via inverse RTCP
        start_tip = list(move.start_pos)
        end_tip = list(move.end_pos)
        self._apply_inverse_rtcp(start_tip)
        self._apply_inverse_rtcp(end_tip)
        # Tip-space XYZ displacement
        tip_axes_d = [ep - sp for sp, ep in zip(start_tip, end_tip)]
        tip_xyz_d2 = sum(d*d for d in tip_axes_d[:3])
        # Determine if tip-space move is ABC-only (no XYZ movement)
        is_tip_abc_only = (tip_xyz_d2 < 1e-12
                           and any(abs(tip_axes_d[idx]) > 1e-9
                                   for idx in rotary_idx
                                   if idx < len(tip_axes_d)))
        # Rotary axes contribution to tip arc length: L * Δθ_rad
        rotary_d2 = 0.
        for idx in rotary_idx:
            if len(tip_axes_d) > idx and tip_axes_d[idx]:
                rotary_d2 += (L * math.radians(tip_axes_d[idx])) ** 2
        if rotary_d2 <= 0.:
            return is_tip_abc_only
        effective_d = math.sqrt(tip_xyz_d2 + rotary_d2)
        if effective_d <= move.move_d:
            return is_tip_abc_only
        # Scale move budgets to reflect true tip path length
        ratio = effective_d / move.move_d
        move.move_d = effective_d
        move.min_move_t *= ratio
        move.delta_v2 *= ratio
        move.mcr_delta_v2 *= ratio
        # Recompute direction ratios for trapq step generation
        inv_move_d = 1. / effective_d
        move.axes_r = [d * inv_move_d for d in move.axes_d]
        return is_tip_abc_only

    def check_move(self, move):
        # Adjust move_d for rotary axis contribution to tip path.
        # Also returns whether the tip-space move is ABC-only.
        is_tip_abc_only = self._adjust_move_d_for_rotary(move)
        # Move is already in PIVOT space (transformed by gcode_move transform)
        limits = self.limits
        xpos, ypos = move.end_pos[:2]
        abc_movement = (len(move.axes_d) > 4
                        and any(d != 0. for d in move.axes_d[4:7]))
        is_abc_only = all(d == 0. for d in move.axes_d[:3]) and abc_movement
        if is_tip_abc_only:
            # Tip-space pure rotary: XYZ pivot movement is RTCP internal.
            # Skip XYZ bounds checks, only validate rotary axis ranges.
            for i in range(3, len(self.axes)):
                pos_idx = self._pos_idx[i]
                if pos_idx >= len(move.axes_d):
                    break
                if (move.axes_d[pos_idx]
                    and (move.end_pos[pos_idx] < limits[i][0]
                         or move.end_pos[pos_idx] > limits[i][1])):
                    if limits[i][0] > limits[i][1]:
                        continue
                    raise move.move_error()
            return
        if (xpos < limits[0][0] or xpos > limits[0][1]
            or ypos < limits[1][0] or ypos > limits[1][1]):
            self._check_endstops(move)
        if is_abc_only:
            return
        if len(move.axes_d) > 2 and not move.axes_d[2]:
            return
        if len(move.axes_d) > 2 and move.axes_d[2]:
            self._check_endstops(move)
            z_ratio = move.move_d / abs(move.axes_d[2])
            move.limit_speed(
                self.max_z_velocity * z_ratio, self.max_z_accel * z_ratio)

    def get_status(self, eventtime):
        axes = [a for a, (l, h) in zip(self.axes, self.limits) if l <= h]
        return {
            'homed_axes': "".join(axes),
            'axis_minimum': self.axes_min,
            'axis_maximum': self.axes_max,
        }

    # gcode_move transform chain (for position display: pivot -> tip)

    def _handle_ready(self):
        gcode_move = self.printer.lookup_object('gcode_move')
        self.next_transform = gcode_move.set_move_transform(self, force=True)

    def move(self, newpos, speed):
        newpos = list(newpos)
        self._apply_rtcp(newpos)
        self.next_transform.move(newpos, speed)

    def get_position(self):
        pos = self.next_transform.get_position()
        self._apply_inverse_rtcp(pos)
        return pos

    # RTCP transform methods

    def _apply_rtcp(self, pos):
        """Tip -> Pivot: given tool tip position and angles, compute pivot XYZ.
           Modifies pos in-place. None values are left unchanged."""
        L = self.tool_length
        if not L:
            return
        if self.rotary_config == 'bc':
            b = math.radians(pos[5]) if len(pos) > 5 and pos[5] is not None else 0.
            c = math.radians(pos[6]) if len(pos) > 6 and pos[6] is not None else 0.
            sb, cb = math.sin(b), math.cos(b)
            sc, cc = math.sin(c), math.cos(c)
            if pos[0] is not None:
                pos[0] -= L * sb * cc
            if pos[1] is not None:
                pos[1] -= L * sb * sc
            if pos[2] is not None:
                pos[2] += L * cb
        else:  # 'ab'
            a = math.radians(pos[4]) if len(pos) > 4 and pos[4] is not None else 0.
            b = math.radians(pos[5]) if len(pos) > 5 and pos[5] is not None else 0.
            ca, sa = math.cos(a), math.sin(a)
            cb, sb = math.cos(b), math.sin(b)
            if pos[0] is not None:
                pos[0] -= L * ca * sb
            if pos[1] is not None:
                pos[1] -= L * sa
            if pos[2] is not None:
                pos[2] += L * ca * cb

    def _apply_inverse_rtcp(self, pos):
        """Pivot -> Tip: given pivot position and angles, compute tip XYZ.
           Modifies pos in-place. None values are left unchanged."""
        L = self.tool_length
        if not L:
            return
        if self.rotary_config == 'bc':
            b = math.radians(pos[5]) if len(pos) > 5 and pos[5] is not None else 0.
            c = math.radians(pos[6]) if len(pos) > 6 and pos[6] is not None else 0.
            sb, cb = math.sin(b), math.cos(b)
            sc, cc = math.sin(c), math.cos(c)
            if pos[0] is not None:
                pos[0] += L * sb * cc
            if pos[1] is not None:
                pos[1] += L * sb * sc
            if pos[2] is not None:
                pos[2] -= L * cb
        else:  # 'ab'
            a = math.radians(pos[4]) if len(pos) > 4 and pos[4] is not None else 0.
            b = math.radians(pos[5]) if len(pos) > 5 and pos[5] is not None else 0.
            ca, sa = math.cos(a), math.sin(a)
            cb, sb = math.cos(b), math.sin(b)
            if pos[0] is not None:
                pos[0] += L * ca * sb
            if pos[1] is not None:
                pos[1] += L * sa
            if pos[2] is not None:
                pos[2] -= L * ca * cb

    def transform_position(self, pos):
        """Called by toolhead.move/set_position/drip_move.
           Converts tip coordinates to pivot coordinates."""
        self._apply_rtcp(pos)
        return pos

    def inverse_transform_position(self, pos):
        """Called by toolhead.get_position.
           Converts pivot coordinates to tip coordinates."""
        self._apply_inverse_rtcp(pos)
        return pos


def load_kinematics(toolhead, config):
    return CartesianRTCPKinematics(toolhead, config)
