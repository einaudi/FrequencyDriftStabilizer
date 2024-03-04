# -*- coding: utf-8 -*-

from copy import copy

import numpy as np


class IIRFilter():

    def __init__(self, ff_coefs, fb_coefs, padding=0):

        # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size
        # print('Filter feedforward order: ', self._ff_order)

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size
        # print('Filter feedback order: ', self._fb_order)

        self._input = np.zeros(self._ff_order) + padding
        self._output = np.zeros(self._fb_order) + padding

    def setFilter(self, ff_coefs, fb_coefs):

         # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size

        self._input = np.zeros(self._ff_order)
        self._output = np.zeros(self._fb_order)

    def update(self, x):

        self._input[1:] = self._input[0:-1]
        self._input[0] = x

        y = np.sum(self._ff_coefs * self._input)
        y += np.sum(self._fb_coefs * self._output)

        self._output[1:] = self._output[0:-1]
        self._output[0] = y

        return y

    def reset(self, padding=0):

        self._input = np.zeros(self._ff_order) + padding
        self._output = np.zeros(self._fb_order) + padding


class PID():

    def __init__(self, dt, kp=1, ki=0, kd=0, sign=1, int_bounds=(-np.inf,np.inf), gain=1, bounds=(1e6,100e6), lead_coef=1):

        self.dt = dt
        self._sign = sign

        self.kp = kp
        self.ki = ki
        self.kd = kd

        self.gain = gain

        self.value_integral = 0
        self.int_bounds = int_bounds

        self.diff_last = 0
        self.lead_coef = lead_coef

        self.bounds = bounds

        self.error_curr = 0
        self.error_last = 0

        self.control_curr = 0
        self.control_last = 0

        self.lock_state = False

    # Settings
    def set_settings(self, kp, ki, kd):

        self.kp = kp
        self.ki = ki
        self.kd = kd

    def set_gain(self, gain):

        self.gain = gain

    def set_timestep(self, dt):

        self.dt = dt

    def set_bounds(self, bounds):

        self.bounds = bounds

    def set_int_bounds(self, int_bounds):

        self.int_bounds = int_bounds

    def setInitialOffset(self, value):

        self.value_integral = value

    def set_params(self, dt, kp=1, ki=0, kd=0, sign=1, int_bounds=(-np.inf,np.inf), gain=1, bounds=(1e6,100e6), lead_coef=1):

        self.dt = dt
        self._sign = sign

        self.kp = kp
        self.ki = ki
        self.kd = kd

        self.int_bounds = int_bounds
        self.lead_coef = lead_coef

        self.gain = gain
        self.bounds = bounds

    # Lock state
    def get_lock_state(self):

        return copy(self.lock_state)

    # Calculations
    def calc_p(self):

        return self.kp * self.error_curr
    
    def calc_i(self):

        self.value_integral += 0.5 * self.ki * self.dt * (self.error_curr + self.error_last)

        # anti wind-up clamping
        if self.value_integral > self.int_bounds[1]:
            self.value_integral = self.int_bounds[1]
        elif self.value_integral < self.int_bounds[0]:
            self.value_integral = self.int_bounds[0]

        return self.value_integral
    
    def calc_d(self):

        ret = (self.error_curr - self.error_last) * self.kd
        ret /= self.dt

        # apply 1st order lowpass filter, lead_coef=1 disables filter
        ret = self.lead_coef*ret + (1-self.lead_coef)*self.diff_last
        self.diff_last = ret

        return ret
    
    def update(self, setpoint, process_variable):

        self.error_last = copy(self.error_curr)
        if self._sign == 1:
            self.error_curr =  setpoint - process_variable
        elif self._sign == -1:
            self.error_curr = - setpoint + process_variable

        # if np.abs(self.error_curr/setpoint) < 0.05:
        #     self.lock_state = True
        # else:
        #     self.lock_state = False

        self.control_last = copy(self.control_curr)

        p = self.calc_p()
        i = self.calc_i()
        d = self.calc_d()

        control = self.gain * (p + i + d)

        if control > self.bounds[1]:
            control = self.bounds[1]
        elif control < self.bounds[0]:
            control = self.bounds[0]

        self.control_curr = control

        return copy(control)
    
    def reset(self):

        self.value_integral = 0

        self.diff_last = 0
        
        self.error_curr = 0
        self.error_last = 0

        self.control_curr = 0
        self.control_last = 0
    

class Loop():

    def __init__(self, dt, ff_coefs, fb_coefs, padding=0, ki=1, sign=1, int_bounds=(-np.inf,np.inf), bounds=(1e6,100e6)):

        # General
        self.bounds = bounds
        self._sign = sign

        # Integrator part
        self.dt = dt
        self.ki = ki
        self.value_integral = 0
        self.int_bounds = int_bounds

        self.error_curr = 0
        self.error_last = 0

        # Lowpass part
        # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size
        # print('Filter feedforward order: ', self._ff_order)

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size
        # print('Filter feedback order: ', self._fb_order)

        self._input = np.zeros(self._ff_order) + padding
        self._output = np.zeros(self._fb_order) + padding

    def setFilter(self, dt, ff_coefs, fb_coefs, ki=0, sign=1, int_bounds=(-np.inf,np.inf), bounds=(1e6,100e6)):

        self.bounds = bounds
        self._sign = sign

        # Integrator
        self.dt = dt
        self.ki = ki
        self.int_bounds = int_bounds

        # Lowpass
        # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size

        self._input = np.zeros(self._ff_order)
        self._output = np.zeros(self._fb_order)

    def setInitialOffset(self, value):

        self.value_integral = value

    # Calculations
    def calc_i(self):

        # trapezoid approximation
        self.value_integral += 0.5 * self.ki * self.dt * (self.error_curr + self.error_last)

        # anti wind-up clamping
        if self.value_integral > self.int_bounds[1]:
            self.value_integral = self.int_bounds[1]
        elif self.value_integral < self.int_bounds[0]:
            self.value_integral = self.int_bounds[0]

        return self.value_integral

    def calc_lowpass(self):

        # Shift input vector and add new value
        self._input[1:] = self._input[0:-1]
        self._input[0] = self.error_curr

        # Calc lowpass response
        ret = np.sum(self._ff_coefs * self._input)
        ret += np.sum(self._fb_coefs * self._output)

        # Shift output vector and add new value
        self._output[1:] = self._output[0:-1]
        self._output[0] = ret

        return ret
    
    def update(self, setpoint, process_variable):

        self.error_last = copy(self.error_curr)
        if self._sign == 1:
            self.error_curr =  setpoint - process_variable
        elif self._sign == -1:
            self.error_curr = - setpoint + process_variable

        # Integral
        I = self.calc_i()

        # Lowpass
        LP = self.calc_lowpass()

        # Summation
        control = I + LP

        # Bounds clamping
        if control > self.bounds[1]:
            control = self.bounds[1]
        elif control < self.bounds[0]:
            control = self.bounds[0]

        return copy(control)

    def reset(self):

        self.value_integral = 0
        
        self.error_curr = 0
        self.error_last = 0

    def set_params(self, dt, ff_coefs, fb_coefs, ki=0, sign=1, int_bounds=(-np.inf,np.inf), bounds=(1e6,100e6)):

        self.bounds = bounds
        self._sign = sign

        # Integrator
        self.dt = dt
        self.ki = ki
        self.int_bounds = int_bounds

        # Lowpass
        # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size

        # Input/output
        padding = self._output[0]
        self._input = np.zeros(self._ff_order) + padding
        self._output = np.zeros(self._fb_order) + padding

    def set_timestep(self, dt):

        self.dt = dt


class LoopDouble():

    def __init__(self, dt, ff_coefs, fb_coefs, padding=0, ki=1, kii=0, sign=1, int_bounds=(-np.inf,np.inf), bounds=(1e6,100e6)):

        # General
        self.bounds = bounds
        self._sign = sign

        # Integrator part
        self.dt = dt
        self.ki = ki
        self.kii = kii
        self.value_integral = 0
        self.value_integral_double = 0
        self.int_bounds = int_bounds

        self.error_curr = 0
        self.error_last = 0

        # Lowpass part
        # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size
        # print('Filter feedforward order: ', self._ff_order)

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size
        # print('Filter feedback order: ', self._fb_order)

        self._input = np.zeros(self._ff_order) + padding
        self._output = np.zeros(self._fb_order) + padding

    def setFilter(self, dt, ff_coefs, fb_coefs, ki=1, kii=0, sign=1, int_bounds=(-np.inf,np.inf), bounds=(1e6,100e6)):

        self.bounds = bounds
        self._sign = sign

        # Integrator
        self.dt = dt
        self.ki = ki
        self.kii = kii
        self.int_bounds = int_bounds

        # Lowpass
        # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size

        self._input = np.zeros(self._ff_order)
        self._output = np.zeros(self._fb_order)

    def setInitialOffset(self, value):

        self.value_integral = 0
        self.value_integral_double = value

    # Calculations
    def calc_i(self):

        # trapezoid approximation
        self.value_integral += 0.5 * self.ki * self.dt * (self.error_curr + self.error_last)

        # anti wind-up clamping
        if self.value_integral > self.int_bounds[1]:
            self.value_integral = self.int_bounds[1]
        elif self.value_integral < self.int_bounds[0]:
            self.value_integral = self.int_bounds[0]

        return self.value_integral

    def calc_ii(self):

        # direct summation
        self.value_integral_double += self.kii * self.dt * self.value_integral/self.ki

        # anti wind-up clamping
        if self.value_integral_double > self.int_bounds[1]:
            self.value_integral_double = self.int_bounds[1]
        elif self.value_integral_double < self.int_bounds[0]:
            self.value_integral_double = self.int_bounds[0]

        return self.value_integral_double

    def calc_lowpass(self):

        # Shift input vector and add new value
        self._input[1:] = self._input[0:-1]
        self._input[0] = self.error_curr

        # Calc lowpass response
        ret = np.sum(self._ff_coefs * self._input)
        ret += np.sum(self._fb_coefs * self._output)

        # Shift output vector and add new value
        self._output[1:] = self._output[0:-1]
        self._output[0] = ret

        return ret
    
    def update(self, setpoint, process_variable):

        self.error_last = copy(self.error_curr)
        if self._sign == 1:
            self.error_curr =  setpoint - process_variable
        elif self._sign == -1:
            self.error_curr = - setpoint + process_variable

        # Integral
        I = self.calc_i()

        # Double integral
        II = self.calc_ii()

        # Lowpass
        LP = self.calc_lowpass()

        # Summation
        control = I + + II + LP

        # Bounds clamping
        if control > self.bounds[1]:
            control = self.bounds[1]
        elif control < self.bounds[0]:
            control = self.bounds[0]

        return copy(control)

    def reset(self):

        self.value_integral = 0
        self.value_integral_double = 0
        
        self.error_curr = 0
        self.error_last = 0

    def set_params(self, dt, ff_coefs, fb_coefs, ki=1, kii=0, sign=1, int_bounds=(-np.inf,np.inf), bounds=(1e6,100e6)):

        self.bounds = bounds
        self._sign = sign

        # Integrator
        self.dt = dt
        self.ki = ki
        self.kii = kii
        self.int_bounds = int_bounds

        # Lowpass
        # multiplies inputs
        self._ff_coefs = np.array(ff_coefs)
        self._ff_order = self._ff_coefs.size

        # multiplies outputs
        self._fb_coefs = np.array(fb_coefs)
        self._fb_order = self._fb_coefs.size

        # Input/output
        padding = self._output[0]
        self._input = np.zeros(self._ff_order) + padding
        self._output = np.zeros(self._fb_order) + padding

    def set_timestep(self, dt):

        self.dt = dt
