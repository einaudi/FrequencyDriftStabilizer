# -*- coding: utf-8 -*-

import os
import time
import importlib
from multiprocessing.shared_memory import SharedMemory

import yaml
import numpy as np

from misc.rate import rate_values
import src.filters as filters
import config.config as cfg


class handlerStabilization():

    def __init__(self, qPOCI, qPICO, semaphore):

        # config
        config_path = os.path.join("./", "config", "devices.yml")
        with open(config_path) as config_file:
            self.devices_config = yaml.safe_load(config_file)

        # Process connection
        self._qPOCI = qPOCI
        self._qPICO = qPICO

        # Shared memory
        self._semaphore = semaphore
        self._shm_iterator = SharedMemory(name='shm_iterator')
        self._shm_val1 = SharedMemory(name='shm_val1')
        self._shm_val2 = SharedMemory(name='shm_val2')
        self._shm_control = SharedMemory(name='shm_control')

        # Data containers
        self._iterator = np.ndarray([1], 'i4', buffer=self._shm_iterator.buf)
        self._f1_cont = np.ndarray([cfg.Npoints], 'f4', buffer=self._shm_val1.buf)
        self._f2_cont = np.ndarray([cfg.Npoints], 'f4', buffer=self._shm_val2.buf)
        self._control_cont = np.ndarray([cfg.Npoints], 'f4', buffer=self._shm_control.buf)

        # Variables
        self._rate = 0.1
        self._setpoint = 0
        self._control = 0

        self._filter = None

        self._lockCounter = 0

        # Flags
        self._lockStatus = False
        self._flagNewData = False
        self._flagSendData = False

        # ADC
        if self.devices_config['ADC'] == 'Dummy':
            self._ADC = DummyADC(self._qPICO)
        elif self.devices_config['ADC'] == 'ADS1256':
            fcLib = importlib.import_module('src.ADC.ADC_ADS1256')
            self._ADC = fcLib.ADC_ADS1256(self._qPICO)
        else:
            print('Wrong ADC selected!', flush=True)
            quit()

        # DAC
        if self.devices_config['DAC'] == 'Dummy':
            self._DAC = DummyDAC(self._qPICO)
        elif self.devices_config['DAC'] == 'DAC8532':
            ddsLib = importlib.import_module('src.DAC.DAC_DAC8532')
            self._DAC = ddsLib.DAC8532Handler(self._qPICO)
        else:
            print('Wrong DAC selected!', flush=True)
            quit()

        self._DACfreq = 0
    
    def queueEmpty(self):
        '''
        Check if commands queue is empty
        
        Returns:
            bool: if queue is empty
        '''
        return self._qPOCI.empty()

    def parseCommand(self):
        '''
        Take one command from queue and parse it. 
        
        Args:
            dict: nested dictionary with command
        '''
        tmp = self._qPOCI.get()
        if tmp['dev'] == 'ADC':
            self._ADC.parseCommand(tmp)
            # Change timestep of PID filter
            if tmp['cmd'] == 'rate':
                self._rate = rate_values[tmp['args']]
                if self._filter is not None:
                    self._filter.set_timestep(rate_values[tmp['args']])
        elif tmp['dev'] == 'DAC':
            self._DAC.parseCommand(tmp)
            # Change DAC frequency
            if tmp['cmd'] == 'freq':
                self._DACfreq = tmp['args']
            # Only dummy
            if self.devices_config['DAC'] == 'Dummy' and self.devices_config['ADC'] == 'Dummy':
                if tmp['cmd'] == 'freq' and self._DAC.isEnabled():
                    self._ADC.changeOffset(self._DACfreq)
                elif tmp['cmd'] == 'en':
                    if tmp['args']:
                        self._ADC.changeOffset(self._DACfreq)
                    else:
                        self._ADC.changeOffset(0)
        elif tmp['dev'] == 'filt':
            self.parseFilterCommand(tmp)

    def sendData(self):

        if self._flagNewData and self._flagSendData:
            # start = time.time()
            if self._semaphore.acquire(block=False):
                i = self._iterator[0]
                d = self._ADC.data()
                self._f1_cont[i] = d[0]
                self._f2_cont[i] = d[1]
                self._control_cont[i] = self._control
                self._iterator[0] = i + 1
                if i+1 >= cfg.Npoints:
                    self._iterator[0] = cfg.Npoints-1
                self._semaphore.release()
            # stop = time.time()
            # print('Memory access time: {:.2e} s'.format(stop - start))

        self._flagNewData = False
            
    # General
    def disconnect(self):
        '''
        Disconnects DAC and ADC. Automatically checks if already connected.
        '''
        self._DAC.disconnect()
        self._ADC.disconnect()
        try:
            self._ADC.releaseGPIO()
        except:
            pass

        self._shm_iterator.close()
        self._shm_val1.close()
        self._shm_val2.close()
        self._shm_control.close()

    def measure(self):
        '''
        If ADC is connected measures frequencies on both channels. Returns true if new data has arrived.
        '''
        return self._ADC.measure()
    
    def wait(self, timeStart, timeStop):
        '''
        If dummy sleep for a period of time equal to rate - (timeStop - timeStart)
        
        Args:
            timeStart, timeStop: timestamps in s to calculate sleep time 
        Returns:
            float: time to wait in s, if negative, then there is a delay in measurement update
        '''
        to_wait = self._rate - (timeStop - timeStart)
        if to_wait > 0:
            if self.devices_config['ADC'] == 'Dummy':
                time.sleep(to_wait)
        else:
            pass
            # print('Delay {:.2e} s'.format(to_wait), flush=True)
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
            # Construct PID filter
            if params['type'] == 'pid':
                filt = filters.PID(**params['params'])
            # Construct IntLowpass filter
            elif params['type'] == 'IntLowpass':
                filt = filters.IntLowpass(**params['params'])
            # Construct DoubleIntLowpass filter
            elif params['type'] == 'DoubleIntLowpass':
                filt = filters.DoubleIntLowpass(**params['params'])
            # Construct DoubleIntDoubleLowpass filter
            elif params['type'] == 'DoubleIntDoubleLowpass':
                filt = filters.DoubleIntDoubleLowpass(**params['params'])

            # Set or update frequency filter
            if self._filter is None:
                self._filter = filt
            else:
                # Check if filter type is the same
                if self._filter.type != params['type']:
                    self._filter = filt
                else:
                    self._filter.setFilter(**params['params'])

        # Reset filter
        elif params['cmd'] == 'reset':
            if self._filter is not None:
                self._filter.reset()
        # Lock engage
        elif params['cmd'] == 'lock':
            if params['args']:
                # soft start of filter, so it continues DAC setting
                self._filter.setInitialOffset(self._DACfreq)
                self._lockStatus = True
                print('Lock engaged!')
            else:
                self._DAC.setFreq(self._DACfreq)
                self._lockStatus = False
                self._lockCounter = 0
                self._qPICO.put({
                        'dev': 'filt',
                        'cmd': 'locked',
                        'args': False
                    })
                # Only dummy
                if self.devices_config['DAC'] == 'Dummy':
                    self._ADC.changeOffset(self._DACfreq)
                print('Lock disengaged!')
        # Send data flag
        elif params['cmd'] == 'data':
            if params['args']:
                self._flagSendData = True
            else:
                self._flagSendData = False
        # Setpoint
        elif params['cmd'] == 'sp':
            self._setpoint = params['args']
            self._ADC.setFreqTarget(params['args'])
            
    def filterUpdate(self):
        '''
        Updates filter output. Calculates process variable and applies lowpass filter if active.
        If locked applies PID filter. Else sets DAC frequency.
        '''
        # Process variable calculation
        pv = self._ADC.fAvg()

        if self._lockStatus:
            # Calculate control
            self._control = self._filter.update(self._setpoint, pv)
            # Set control value
            # start = time.time()
            self._DAC.setFreq(self._control)
            # stop = time.time()
            # print('DAC: {:.6}'.format(stop-start), flush=True)
            # Only dummy
            if self.devices_config['DAC'] == 'Dummy':
                self._ADC.changeOffset(self._control)

            # Check if locked
            if abs(self._setpoint - pv) <= cfg.errorMargin:
                self._lockCounter += 1
                if self._lockCounter == 100:
                    self._qPICO.put({
                        'dev': 'filt',
                        'cmd': 'locked',
                        'args': True
                    })
                elif self._lockCounter > 100:
                    self._lockCounter = 101
            else:
                if self._lockCounter >= 100:
                    self._qPICO.put({
                            'dev': 'filt',
                            'cmd': 'locked',
                            'args': False
                        })
                self._lockCounter = 0


        self._flagNewData = True


class DummyADC():

    def __init__(self, conn):

        self._qPICO = conn
        self._channels = '1'

        self._rate = 0.1
        self._f = [0, 0]
        self._fAvg = 0
        self._fOffset = 0

        self._flagConnected = False

        self._fDisturbance = 0.1 # Hz - input of disturbance
        self._ADisturbance = 0.01 # V - amplitude of disturbance

        print('Dummy ADC handler initiated!', flush=True)

    def parseCommand(self, cmdDict):

        if cmdDict['cmd'] == 'rate':
            self._rate = rate_values[cmdDict['args']]
        elif cmdDict['cmd'] == 'channels':
            self._channels = cmdDict['args']
        elif cmdDict['cmd'] == 'devices':
            ret = self.enumerate_devices()
            self._qPICO.put({'dev': 'ADC', 'cmd': 'devices', 'args': ret})
        elif cmdDict['cmd'] == 'connect':
            self.connect()
            self._qPICO.put({'dev': 'ADC', 'cmd': 'connection', 'args': self._flagConnected})
        elif cmdDict['cmd'] == 'disconnect':
            self.disconnect()
            self._qPICO.put({'dev': 'ADC', 'cmd': 'connection', 'args': self._flagConnected})

    def fAvg(self):

        return self._fAvg

    def data(self):

        return self._f

    def setFreqTarget(self, fTarget):

        return True

    # Connection
    def enumerate_devices(self):
        
        return ['Dummy']
    
    def connect(self):

        if not self._flagConnected:
            self._flagConnected = True
            print('Dummy ADC connected!', flush=True)
            return True
        else:
            return False

    def disconnect(self):

        if self._flagConnected:
            self._flagConnected = False
            print('Dummy ADC disconnected!', flush=True)
            return True
        else:
            return False
    
    # Measurement
    def read_freq(self):

        if self._flagConnected:
            f1 = 0.1 
            f1 += np.random.normal(0, 0.001)
            f1 += self._ADisturbance*np.sin(2*np.pi*self._fDisturbance*time.time()) 
            f1 += self._fOffset

            f2 = 0.1 
            f2 += np.random.normal(0, 0.001)
            f2 += self._ADisturbance*np.sin(2*np.pi*self._fDisturbance*time.time())
            f2 += self._fOffset

            ret = [f1, f2]
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
                    # self._qPICO.put({'dev': 'ADC', 'cmd': 'data', 'args': self._f})
                except ValueError:
                    return False
        
            return True
        else:
            return False

    # Only dummy
    def changeOffset(self, offset):

        self._fOffset = offset


class DummyDAC():

    def __init__(self, conn):

        self._qPICO = conn

        self._flagConnected = False
        self._flagEnabled = False

        print('Dummy DAC handler initiated!', flush=True)

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

        # DAC connection
        if params['cmd'] == 'connect':
            self.connect()
        elif params['cmd'] == 'disconnect':
            self.disconnect()
        elif params['cmd'] == 'devices':
            ret = self.enumerate_devices()
            self._qPICO.put({'dev': 'DAC', 'cmd': 'devices', 'args': ret})
        # DAC enable
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

    def connect(self):

        if not self._flagConnected:
            self._flagConnected = True
            print('Dummy DAC connected!', flush=True)
            self._qPICO.put({'dev': 'DAC', 'cmd': 'connection', 'args': 1})
            return True
            
        print('Already connected to DAC!')
        return True

    def disconnect(self):

        self.setFreq(0)
        self._flagConnected = False
        self._qPICO.put({'dev': 'DAC', 'cmd': 'connection', 'args': 0})
        print('Dummy DAC disconnected!', flush=True)

    def setFreq(self, freq):

        return True
    
    def setAmp(self, amp):

        return True


class DummyConnection():
    def __init__(self):
        return 
    def send(self, cmd):
        return True
