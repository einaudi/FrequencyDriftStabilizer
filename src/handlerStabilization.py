# -*- coding: utf-8 -*-

import os
import time
import importlib

import yaml
import numpy as np

from misc.commands import cmds_values
import src.filters as filters


waitOffset = 0.001
phaseLockMargin = 1 # Hz
phaseLockCounterLimit = 100


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
        self._mode = 0 # 0 for frequency, 1 for phase
        self._setpoint = 0
        self._phasePrev = 0
        self._control = 0

        self._lowpass = None
        self._filterFreq = None
        self._filterPhase = None

        # Flags
        self._lockStatus = False
        self._flagLowpass = False
        self._flagLowpassActive = False
        self._flagPhaseLock = False # try to phase lock
        self._counterPhaseLock = 0 # count if frequency is locked
        self._activeFreqFilter = ''
        self._activePhaseFilter = ''

        # Frequency counter
        if self.devices_config['FrequencyCounter'] == 'Dummy':
            self._FC = DummyFC(self._conn) 
        elif self.devices_config['FrequencyCounter'] == 'FXE':
            fcLib = importlib.import_module('src.FrequencyCounters.KK_FXE')
            self._FC = fcLib.FXEHandler(self._conn)
        elif self.devices_config['FrequencyCounter'] == 'Keysight':
            fcLib = importlib.import_module('src.FrequencyCounters.FC53230A')
            self._FC = fcLib.FC53230A(self._conn)

        # DDS
        if self.devices_config['DDS'] == 'Dummy':
            self._DDS = DummyDDS(self._conn)
        elif self.devices_config['DDS'] == 'AD9912':
            ddsLib = importlib.import_module('src.DDS.DDS_AD9912')
            self._DDS = ddsLib.AD9912Handler(self._conn)
        elif self.devices_config['DDS'] == 'DG4162':
            ddsLib = importlib.import_module('src.DDS.DG4162')
            self._DDS = ddsLib.DG4162Handler(self._conn)

        self._DDSfreq = 0
        self._DDSphase = 0
    
    def queueEmpty(self):
        '''
        Check if commands queue is empty
        
        Returns:
            bool: if queue is empty
        '''
        return self._q.empty()

    def parseCommand(self):
        '''
        Take one command from queue and parse it. 
        
        Args:
            dict: nested dictionary with command
        '''
        tmp = self._q.get()
        if tmp['dev'] == 'FC':
            self._FC.parseCommand(tmp)
            # Change timestep of PID filter
            if tmp['cmd'] == 'rate':
                self._rate = cmds_values['rate'][tmp['args']]
                if self._filterFreq is not None:
                    self._filterFreq.set_timestep(cmds_values['rate'][tmp['args']])
                if self._filterPhase is not None:
                    self._filterPhase.set_timestep(cmds_values['rate'][tmp['args']])
        elif tmp['dev'] == 'DDS':
            self._DDS.parseCommand(tmp)
            # Change DDS frequency
            if tmp['cmd'] == 'freq':
                self._DDSfreq = tmp['args']
                # Only dummy
                if self.devices_config['DDS'] == 'Dummy':
                    self._FC.changeOffset(self._DDSfreq)
            # Change DDS phase
            if tmp['cmd'] == 'phase':
                self._DDSphase = tmp['args']
        elif tmp['dev'] == 'filt':
            self.parseFilterCommand(tmp)

    # General
    def disconnect(self):
        '''
        Disconnects DDS and Frequency Counter. Automatically checks if already connected.
        '''
        self._DDS.disconnect()
        self._FC.disconnect()

    def measure(self):
        '''
        If Frequency Counter is connected measures frequencies on both channels. Returns true if new data has arrived.
        '''
        return self._FC.measure()
    
    def wait(self, timeStart, timeStop):
        '''
        Sleep for a period of time equal to rate - (timeStop - timeStart) - waitOffset
        
        Args:
            timeStart, timeStop: timestamps in s to calculate sleep time 
        Returns:
            float: time to wait in s, if negative, then there is a delay in measurement update
        '''
        # print(self._rate)
        # print(timeStop-timeStart)
        to_wait = self._rate - (timeStop - timeStart)
        # to_wait_offset = 0.5*to_wait - waitOffset
        # if to_wait_offset > 0:
        #     time.sleep(to_wait_offset)
        return to_wait

    # Filter
    def parseFilterCommand(self, params):
        '''
        Parse commands specific for filter operation
        
        Args:
            params: dictionary with command for filter operation
        '''
        # Filter construction
        if params['cmd'] == 'filt':
            # Construct frequency loop filter
            if params['type'] == 'loop-freq':
                # Create new filter
                if self._filterFreq is None or self._activeFreqFilter != params['type']:
                    self._filterFreq = filters.Loop(
                        **params['params']
                    )
                    self._activeFreqFilter = params['type']
                # Update filter settings
                else:
                    self._filterFreq.set_params(**params['params'])
            # Construct phase loop filter
            elif params['type'] == 'loop-phase':
                # Create new filter
                if self._filterPhase is None or self._activePhaseFilter != params['type']:
                    self._filterPhase = filters.Loop(
                        **params['params']
                    )
                    self._activePhaseFilter = params['type']
                # Update filter settings
                else:
                    self._filterPhase.set_params(**params['params'])
            # Construct frequency PID
            elif params['type'] == 'pid-freq':
                # Create new filter
                if self._filterFreq is None or self._activeFreqFilter != params['type']:
                    self._filterFreq = filters.PID(
                        **params['params']
                    )
                    self._activeFreqFilter = params['type']
                # Update filter settings
                else:
                    self._filterFreq.set_params(**params['params'])
            # Construct phase PID
            elif params['type'] == 'pid-phase':
                # Create new filter
                if self._filterPhase is None or self._activePhaseFilter != params['type']:
                    self._filterPhase = filters.PID(
                        **params['params']
                    )
                    self._activePhaseFilter = params['type']
                # Update filter settings
                else:
                    self._filterPhase.set_params(**params['params'])
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
                print('Lowpass activated!', flush=True)
            else:
                self._flagLowpassActive = False
                print('Lowpass deactivated!', flush=True)
        # Reset filters
        elif params['cmd'] == 'reset':
            if self._filterFreq is not None:
                self._filterFreq.reset()
            if self._filterPhase is not None:
                self._filterPhase.reset()
            if self._lowpass is not None:
                self._lowpass.reset(padding=self._FC.fAvg())
        # Lock engage
        elif params['cmd'] == 'lock':
            if params['args']:
                # soft start of filter, so it continues DDS setting
                self._filterFreq.setInitialOffset(self._DDSfreq)
                if self._flagPhaseLock:
                    self._filterPhase.setInitialOffset(self._DDSfreq)
                self._lockStatus = True
                print('Lock engaged!')
            else:
                self._DDS.setFreq(self._DDSfreq)
                self._lockStatus = False
                if self._mode: # if in phase mode switch to frequency with active phase lock
                    self._mode = 0
                    self._flagPhaseLock = True
                    self._counterPhaseLock = 0
                # Only dummy
                if self.devices_config['DDS'] == 'Dummy':
                    self._FC.changeOffset(self._control)
                print('Lock disengaged!')
                self._conn.send({'dev': 'filt', 'cmd': 'phaseLock', 'args': 0})
        # Setpoint
        elif params['cmd'] == 'sp':
            self._setpoint = params['args']
            self._FC.setFreqTarget(params['args'])
        # Mode
        elif params['cmd'] == 'mode':
            if params['args'] == 'Phase':
                print('Mode changed to PLL!')
                self._flagPhaseLock = True
            else:
                print('Mode changed to FLL!')
                self._flagPhaseLock = False
                self._mode = 0
            
    def filterUpdate(self):
        '''
        Updates filter output. Calculates process variable and applies lowpass filter if active.
        If locked applies PID filter. Else sets DDS frequency.
        '''
        # Process variable calculation
        # Lowpass
        if self._flagLowpass and self._flagLowpassActive:
            pv = self._lowpass.update(self._FC.fAvg())
        else:
            pv = self._FC.fAvg()
        
        self._conn.send({'dev': 'filt', 'cmd': 'avg', 'args': pv})

        # PLL/FLL if locked
        if self._lockStatus:
            # Try to acquire phase lock
            if self._flagPhaseLock:
                if abs(self._setpoint - pv) < phaseLockMargin:
                    self._counterPhaseLock += 1
                if self._counterPhaseLock >= phaseLockCounterLimit:
                    self._mode = 1
                    self._flagPhaseLock = False
                    self._conn.send({'dev': 'filt', 'cmd': 'phaseLock', 'args': 1})
            # Check if still frequency locked
            if self._mode:
                if abs(self._setpoint - pv) > phaseLockMargin:
                    self._counterPhaseLock -= 1
                if self._counterPhaseLock <= 0:
                    self._mode = 0
                    self._flagPhaseLock = True
                    self._conn.send({'dev': 'filt', 'cmd': 'phaseLock', 'args': 0})

        # Process variable integration if phase mode
        if self._mode:
            # pv = self._setpoint - pv
            pv = pv - self._setpoint
            pv *= self._rate
            pv = self._phasePrev + pv # integration to retrieve phase
            self._phasePrev = pv

        self._conn.send({'dev': 'filt', 'cmd': 'pv', 'args': pv})

        if self._lockStatus:
            # Calculate control
            if self._mode == 1:
                self._control = self._filterPhase.update(0, pv)
            else:
                self._control = self._filterFreq.update(self._setpoint, pv)
            # Set control value
            self._DDS.setFreq(self._control)
            self._conn.send({'dev': 'filt', 'cmd': 'control', 'args': self._control})
            # Only dummy
            if self.devices_config['DDS'] == 'Dummy':
                self._FC.changeOffset(self._control)


class DummyFC():

    def __init__(self, conn):

        self._conn = conn
        self._channels = '1'

        self._rate = 0.1
        self._f = [0, 0]
        self._fAvg = 0
        self._fOffset = 0

        self._flagConnected = False

        print('Dummy Frequency Counter handler initiated!', flush=True)

    def parseCommand(self, cmdDict):

        if cmdDict['cmd'] == 'rate':
            self._rate = cmds_values['rate'][cmdDict['args']]
        elif cmdDict['cmd'] == 'channels':
            self._channels = cmdDict['args']
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
            f1 += np.random.normal(0, 0.2)
            f1 += 10*np.sin(np.pi*time.time()) 
            f1 += self._fOffset

            f2 = 5e6 
            f2 += np.random.normal(0, 0.2)
            f2 += 10*np.sin(np.pi*time.time())
            f2 += self._fOffset

            if self._channels == '1':
                ret = [
                    '{:e}'.format(f1),
                    '{:e}'.format(f1)
                ]
            elif self._channels == '2':
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
        elif params['cmd'] == 'disconnect':
            self.disconnect()
        elif params['cmd'] == 'devices':
            ret = self.enumerate_devices()
            self._conn.send({'dev': 'DDS', 'cmd': 'devices', 'args': ret})
        # DDS enable
        elif params['cmd'] == 'en':
            if self._flagConnected:
                if params['args']:
                    self._flagEnabled = True
                else:
                    self._flagEnabled = False
        # Frequency
        elif params['cmd'] == 'freq':
            self.setFreq(params['args'])
        # Amplitude
        elif params['cmd'] == 'amp':
            self.setAmp(params['args'])

    def enumerate_devices(self):

        return ['Dummy']

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
