# -*- coding: utf-8 -*-

from src.KK_FXE import *
from misc.kk_commands import cmds_values
import src.filters as filters


class handlerStabilization(FXEHandler):

    def __init__(self, q, connFXE):

        super().__init__(q, connFXE)

        # Variables
        self._setpoint = 0
        self._control = 0

        self._filter = None

        # DDS
        self._DDSfreq = 0
        self._DDSamp = 0

        # Flags
        self._lockStatus = False
        self._flagDDSEnabled = False
        self._flagLowpass = False
        self._flagLowpassActive = False

    def parseCommand(self):
        
        tmp = self._q.get()
        if tmp['dev'] == 'FXE':
            self.parseFXECommand(tmp)
            if tmp['cmd'] == 'rate' and self._filter is not None:
                self._filter.set_timestep(cmds_values['rate'][tmp['args']])
        elif tmp['dev'] == 'DDS':
            self.parseDDSCommand(tmp)
        elif tmp['dev'] == 'filt':
            self.parseFilterCommand(tmp)

    # DDS
    def parseDDSCommand(self, params):

        # DDS enable
        if params['cmd'] == 'en':
            if params['args']:
                self._flagDDSEnabled = True
            else:
                self._flagDDSEnabled = False
        elif params['cmd'] == 'freq':
            if not self._lockStatus and self._flagDDSEnabled:
                self._control = params['args']

    # Filter
    def parseFilterCommand(self, params):

        # Filter construction
        if params['cmd'] == 'filt':
            # Construct PID
            if params['type'] == 'pid':
                # Create new filter
                if self._filter is None:
                    self._filter = filters.PID(
                        **params['params']
                    )
                # Update filter settings
                else:
                    self._filter.set_params(**params['params'])
            # Construct lowpass
            elif params['type'] == 'lowpass':
                self._lowpass = filters.IIRFilter(
                        params['params']['ff_coefs'],
                        params['params']['fb_coefs']
                    )
                self._flagLowpass = True
        # Apply lowpass filter
        elif params['cmd'] == 'lpApply':
            if params['args']:
                self._flagLowpassActive = True
            else:
                self._flagLowpassActive = False
        # Reset filters
        elif params['cmd'] == 'reset':
            if self._filter is not None:
                self._filter.reset()
            if self._lowpass is not None:
                self._lowpass.reset()
        # Lock engage
        elif params['cmd'] == 'lock':
            if params['args']:
                self._lockStatus = True
            else:
                self._lockStatus = False
        # Setpoint
        elif params['cmd'] == 'sp':
            self._setpoint = params['args']

    def filterUpdate(self):

        if self._flagLowpass and self._flagLowpassActive:
            pv = self._lowpass.update(self._fAvg)
        else:
            pv = self._fAvg
        self._conn.send({'cmd': 'pv', 'args': pv})

        if self._lockStatus:
            self._control = self._filter.update(self._setpoint, pv)
            self._conn.send({'cmd': 'control', 'args': self._control})

        # Outside of lock if because manual DDS also affects that
        if self._flagDDSEnabled:
            'XXX'


class handlerStabilizationDummy(FXEHandlerDummy):

    def __init__(self, q, connFXE):

        super().__init__(q, connFXE)

        # Variables
        self._setpoint = 0
        self._control = 0

        self._filter = None

        # DDS
        self._DDSfreq = 0
        self._DDSamp = 0

        # Flags
        self._lockStatus = False
        self._flagDDSEnabled = False
        self._flagLowpass = False
        self._flagLowpassActive = False

    def parseCommand(self):
        
        tmp = self._q.get()
        if tmp['dev'] == 'FXE':
            self.parseFXECommand(tmp)
            if tmp['cmd'] == 'rate' and self._filter is not None:
                self._filter.set_timestep(cmds_values['rate'][tmp['args']])
        elif tmp['dev'] == 'DDS':
            self.parseDDSCommand(tmp)
        elif tmp['dev'] == 'filt':
            self.parseFilterCommand(tmp)

    # DDS
    def parseDDSCommand(self, params):

        # DDS enable
        if params['cmd'] == 'en':
            if params['args']:
                self._flagDDSEnabled = True
                if not self._lockStatus:
                    self._control = self._DDSfreq
            else:
                self._flagDDSEnabled = False
                self._control = 0
        elif params['cmd'] == 'freq':
            self._DDSfreq = params['args']
            if (not self._lockStatus) and self._flagDDSEnabled:
                self._control = self._DDSfreq

    # Filter
    def parseFilterCommand(self, params):

        # Filter construction
        if params['cmd'] == 'filt':
            # Construct PID
            if params['type'] == 'pid':
                # Create new filter
                if self._filter is None:
                    self._filter = filters.PID(
                        **params['params']
                    )
                # Update filter settings
                else:
                    self._filter.set_params(**params['params'])
            # Construct lowpass
            elif params['type'] == 'lowpass':
                self._lowpass = filters.IIRFilter(
                        params['params']['ff_coefs'],
                        params['params']['fb_coefs']
                    )
                self._flagLowpass = True
        # Apply lowpass filter
        elif params['cmd'] == 'lpApply':
            if params['args']:
                self._flagLowpassActive = True
            else:
                self._flagLowpassActive = False
        # Reset filters
        elif params['cmd'] == 'reset':
            if self._filter is not None:
                self._filter.reset()
            if self._lowpass is not None:
                self._lowpass.reset()
        # Lock engage
        elif params['cmd'] == 'lock':
            if params['args']:
                self._lockStatus = True
            else:
                self._lockStatus = False
        # Setpoint
        elif params['cmd'] == 'sp':
            self._setpoint = params['args']

    def filterUpdate(self):

        if self._flagLowpass and self._flagLowpassActive:
            pv = self._lowpass.update(self._fAvg)
        else:
            pv = self._fAvg
        self._conn.send({'cmd': 'pv', 'args': pv})

        if self._lockStatus:
            self._control = self._filter.update(self._setpoint, pv)
            self._conn.send({'cmd': 'control', 'args': self._control})

        # Outside of lock if because manual DDS also affects that
        self.changeOffset(self._control)