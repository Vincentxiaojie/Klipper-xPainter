# Code for handling multi-axis kinematics (XYZABC, up to 7 axes)
#
# Based on cartesian.py - supports X, Y, Z, A, B, C, E axes
#
import logging
import stepper

class CartABCKinematics:
    def __init__(self, toolhead, config):
        self.printer = config.get_printer()
        # Determine which axes are configured
        self.axes = 'xyz'
        for axis in 'abc':
            if config.has_section('stepper_' + axis):
                self.axes += axis
        # Setup axis rails (all same as cartesian.py, just more axes)
        self.rails = [stepper.LookupMultiRail(config.getsection('stepper_' + n))
                      for n in self.axes]
        print(f"DEBUG cartesian_abc: {len(self.rails)} rails created, {[r.get_name() for r in self.rails]}")
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
        print(f"DEBUG cartesian_abc: _pos_idx = {self._pos_idx}")
    def get_steppers(self):
        return [s for rail in self.rails for s in rail.get_steppers()]
    def calc_position(self, stepper_positions):
        return [stepper_positions[rail.get_name()] for rail in self.rails]
    def update_limits(self, i, range):
        l, h = self.limits[i]
        if l <= h:
            self.limits[i] = range
    def set_position(self, newpos, homing_axes):
        # Extend toolhead.commanded_pos if needed for extra axes
        toolhead = self.printer.lookup_object('toolhead')
        while len(toolhead.commanded_pos) < len(newpos):
            toolhead.commanded_pos.append(0.0)
        # Build rail-coordinate position array: [X, Y, Z, A, B, C]
        # from commanded_pos format: [X, Y, Z, E, A, B, C]
        rail_pos = [0.] * 6
        for i, rail in enumerate(self.rails):
            pos_idx = self._pos_idx[i]
            if pos_idx < len(newpos):
                rail_pos[i] = newpos[pos_idx]
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
        pos_idx = self._pos_idx[axis]
        position_min, position_max = rail.get_range()
        hi = rail.get_homing_info()
        homepos = [None] * 7
        homepos[pos_idx] = hi.position_endstop
        # Determine primary direction from commanded position
        curpos = rail.get_commanded_position()
        if curpos > hi.position_endstop:
            first_dir = False  # home negative (toward endstop)
        elif curpos < hi.position_endstop:
            first_dir = True   # home positive (toward endstop)
        else:
            first_dir = hi.positive_dir  # at endstop, use config default
        # Two attempts: primary direction (1.5x), then opposite (2.5x)
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
            try:
                homing_state.home_rails([rail], forcepos, homepos)
                return
            except self.printer.command_error as e:
                last_error = e
                continue
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
                    # Skip homing check for ABC axes (continuous rotation)
                    if i >= 3:
                        continue
                    raise move.move_error("Must home axis first")
                raise move.move_error()
    def check_move(self, move):
        limits = self.limits
        xpos, ypos = move.end_pos[:2]
        abc_movement = (len(move.axes_d) > 4
                        and any(d != 0. for d in move.axes_d[4:7]))
        is_abc_only = all(d == 0. for d in move.axes_d[:3]) and abc_movement
        print(f"DEBUG check_move: axes_r={move.axes_r}, is_abc_only={is_abc_only}")
        if (xpos < limits[0][0] or xpos > limits[0][1]
            or ypos < limits[1][0] or ypos > limits[1][1]):
            self._check_endstops(move)
        if is_abc_only:
            # Pure rotational move - don't apply XY/Z checks
            return
        if len(move.axes_d) > 2 and not move.axes_d[2]:
            return
        if len(move.axes_d) > 2 and move.axes_d[2]:
            self._check_endstops(move)
            z_ratio = move.move_d / abs(move.axes_d[2])
            move.limit_speed(
                self.max_z_velocity * z_ratio, self.max_z_accel * z_ratio)
            self._check_endstops(move)
    def get_status(self, eventtime):
        axes = [a for a, (l, h) in zip(self.axes, self.limits) if l <= h]
        return {
            'homed_axes': "".join(axes),
            'axis_minimum': self.axes_min,
            'axis_maximum': self.axes_max,
        }

def load_kinematics(toolhead, config):
    return CartABCKinematics(toolhead, config)
