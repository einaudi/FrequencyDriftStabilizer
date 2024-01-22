# -*- coding: utf-8 -*-

import os
import time

import yaml
import numpy as np

from src.FrequencyCounters.KK_FXE import FXEHandler
from src.FrequencyCounters.FC53230A import FC53230A
from src.DDS.DDS_AD9912 import AD9912Handler
from src.DDS.DG4162 import DG4162Handler
from misc.commands import cmds_values
import src.filters as filters


class handlerStabilization():

    def __init__(self, q, conn):

        # config
        config_path = os.path.join("./", "config", "devices.yml")
        with open(config_path) as config_file:
            self.devices_config = yaml.safe_load(config_file)

        # Process connection
        self._q = q
        self._conn = conn

        # Variables
        self._rate = 0.1
        self._fAvg = 0
        self._setpoint = 0
        self._control = 0

        self._filter = None

        # Frequency counter
        if self.devices_config['FrequencyCounter'] == 'Dummy':
            self._FC = DummyFC(self._conn) 
        elif self.devices_config['FrequencyCounter'] == 'FXE':
            self._FC = FXEHandler(self._conn)
        elif self.devices_config['FrequencyCounter'] == 'Keysight':
            self._FC = FC53230A(self._conn)

        # DDS
        if self.devices_config['DDS'] == 'Dummy':
            self._DDS = DummyDDS(self._conn)
        elif self.devices_config['DDS'] == 'AD9912':
            self._DDS = AD9912Handler(self._conn)
        elif self.devices_config['DDS'] == 'DG4162':
            self._DDS = DG4162Handler(self._conn)

        self._DDSfreq = 0

        # Flags
        self._lockStatus = False
        self._flagLowpass = False
        self._flagLowpassActive = False
    
    def queueEmpty(self):

        return self._q.empty()

    def parseCommand(self):
        
        tmp = self._q.get()
        if tmp['dev'] == 'FC':
            self._FC.parseCommand(tmp)
            # Change timestep of PID filter
            if tmp['cmd'] == 'rate':
                self._rate = cmds_values['rate'][tmp['args']]
                if self._filter is not None:
                    self._filter.set_timestep(cmds_values['rate'][tmp['args']])
        elif tmp['dev'] == 'DDS':
            self._DDS.parseCommand(tmp)
            # Change DDS frequency
            if tmp['cmd'] == 'freq':
                self._DDSfreq = tmp['args']
        elif tmp['dev'] == 'filt':
            self.parseFilterCommand(tmp)

    # General
    def disconnect(self):

        self._DDS.disconnect()
        self._FC.disconnect()

    def measure(self):

        self._FC.measure()
    
    def wait(self, timeStart, timeStop):

        to_wait = self._rate - (timeStop - timeStart)
        if to_wait > 0:
            time.sleep(to_wait)
        return to_wait

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
                        params['params']['fb_coefs'],
                        padding=self._FC.fAvg()
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
                self._lowpass.reset(padding=self._FC.fAvg())
        # Lock engage
        elif params['cmd'] == 'lock':
            if params['args']:
                self._lockStatus = True
            else:
                self._lockStatus = False
                self._control = self._DDSfreq
        # Setpoint
        elif params['cmd'] == 'sp':
            self._setpoint = params['args']
            self._FC.setFreqTarget(params['args'])

    def filterUpdate(self):

        if self._flagLowpass and self._flagLowpassActive:
            pv = self._lowpass.update(self._FC.fAvg())
        else:
            pv = self._FC.fAvg()
        self._conn.send({'dev': 'filt', 'cmd': 'pv', 'args': pv})

        if self._lockStatus:
            self._control = self._filter.update(self._setpoint, pv)
            self._DDS.setFreq(self._control)
            self._conn.send({'dev': 'filt', 'cmd': 'control', 'args': self._control})
            if self.devices_config['DDS'] == 'Dummy':
                self._FC.changeOffset(self._control)
        else:
            self._DDS.setFreq(self._DDSfreq)
            if self.devices_config['DDS'] == 'Dummy':
                self._FC.changeOffset(self._DDSfreq)


class DummyFC():

    def __init__(self, conn):

        self._conn = conn

        self._rate = 0.1
        self._f = [0, 0]
        self._fAvg = 0
        self._fOffset = 0

        self._flagConnected = False

        print('Dummy Frequency Counter handler initiated!', flush=True)

    def parseCommand(self, cmdDict):

        if cmdDict['cmd'] == 'rate':
            self._rate = cmds_values['rate'][cmdDict['args']]
        elif cmdDict['cmd'] == 'devices':
            ret = self.enumerate_devices()
            self._conn.send({'dev': 'FC', 'cmd': 'devices', 'args': ret})
        elif cmdDict['cmd'] == 'connect':
            self.connect(cmdDict['args'])
            self._conn.send({'dev': 'FC', 'cmd': 'connection', 'args': self._flagConnected})
        elif cmdDict['cmd'] == 'disconnect':
            self.disconnect()
            self._conn.send({'dev': 'FC', 'cmd': 'connection', 'args': self._flagConnected})

    def fAvg(self):

        return self._fAvg

    def setFreqTarget(self, fTarget):

        return True

    # Connection
    def enumerate_devices(self):
        
        return ['Dummy']
    
    def connect(self, address):

        if not self._flagConnected:
            self._flagConnected = True
            print('Frequency counter connected!', flush=True)
            return True
        else:
            return False

    def disconnect(self):

        if self._flagConnected:
            self._flagConnected = False
            print('Frequency counter disconnected!', flush=True)
            return True
        else:
            return False
    
    # Measurement
    def read_freq(self):

        if self._flagConnected:
            f1 = 5e6 
            f1 += np.random.normal(0, 0.1)
            f1 += 10*np.sin(np.pi*time.time()) 
            f1 += self._fOffset

            f2 = 5e6 
            f2 += np.random.normal(0, 0.1)
            f2 += 10*np.sin(np.pi*time.time())
            f2 += self._fOffset

            ret = [
                '{:e}'.format(f1),
                '{:e}'.format(f2)
            ]
            return ret
        else:
            return None

    def measure(self):

        if self._flagConnected:
            data = self.read_freq()
            if data is not None:
                try:
                    self._f[0] = float(data[0])
                    self._f[1] = float(data[1])
                    self._fAvg = np.average(self._f)
                    self._conn.send({'dev': 'FC', 'cmd': 'data', 'args': self._f})
                except ValueError:
                    return False
        
            return True
        else:
            return False

    # Only dummy
    def changeOffset(self, offset):

        self._fOffset = offset


class DummyDDS():

    def __init__(self, conn):

        self._conn = conn

        self._flagConnected = False
        self._flagEnabled = False

        print('Dummy DDS handler initiated!', flush=True)

    def isConnected(self):

        if self._flagConnected:
            return True
        else:
            return False

    def isEnabled(self):

        if self._flagEnabled:
            return True
        else:
            return False

    def parseCommand(self, params):

        # DDS connection
        if params['cmd'] == 'connect':
            self.connect(params['args'])
        elif params['cmd'] == 'disonnect':
            self.disconnect()
        # DDS enable
        elif params['cmd'] == 'en':
            if self._flagConnected:
                if params['args']:
                    self._flagEnabled = True
                else:
                    self._flagEnabled = False
        # Amplitude
        elif params['cmd'] == 'amp':
            self.setAmp(params['args'])

    def connect(self, ip):

        if not self._flagConnected:
            self._flagConnected = True
            print('DDS connected!', flush=True)
            self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 1})
            return True
            
        print('Already connected to DDS!')
        return True

    def disconnect(self):

        self.setFreq(0)
        self._flagConnected = False
        self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 0})
        print('DDS disconnected!', flush=True)

    def setFreq(self, freq):

        return True

    def setAmp(self, amp):

        return True

class DummyConnection():
    def __init__(self):
        return 
    def send(self, cmd):
        return True
