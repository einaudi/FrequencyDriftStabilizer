# -*- coding: utf-8 -*-

from src.FrequencyCounters.ADS1256_lib.ADS1256 import ADS1256, ADS1256_DRATE_E, ADS1256_GAIN_E

from misc.rate import rate_values

import numpy as np


rate_dict = {
    '33us': 'ADS1256_30000SPS',
    '66us': 'ADS1256_15000SPS',
    '133us': 'ADS1256_7500SPS',
    '266us': 'ADS1256_3750SPS',
    '500us': 'ADS1256_2000SPS',
    '1ms': 'ADS1256_1000SPS',
    '2ms': 'ADS1256_500SPS',
    '10ms': 'ADS1256_100SPS',
    '16ms': 'ADS1256_60SPS',
    '20ms': 'ADS1256_50SPS',
    '33ms': 'ADS1256_30SPS',
    '40ms': 'ADS1256_25SPS',
    '66ms': 'ADS1256_15SPS',
    '100ms': 'ADS1256_10SPS',
    '200ms': 'ADS1256_5SPS',
    '400ms': 'ADS1256_2d5SPS'
}

class ADC_ADS1256():

    def __init__(self, conn):

        self._qPICO = conn
        self._channels = '1'

        self._rate = 0.1
        self._f = [0, 0]
        self._fAvg = 0
        self._fOffset = 0

        self._flagConnected = False

        self.adc = ADS1256()
        self.adc.ADS1256_init()
        self.adc.ADS1256_SetChannel(0)

        print('ADS1256 Frequency Counter handler initiated!', flush=True)

    def parseCommand(self, cmdDict):

        if cmdDict['cmd'] == 'rate':
            self._rate = rate_values[cmdDict['args']]
            self.adc.ADS1256_ConfigADC(
                ADS1256_GAIN_E['ADS1256_GAIN_1'],
                ADS1256_DRATE_E[rate_dict[cmdDict['args']]]
            )
        elif cmdDict['cmd'] == 'channels':
            self.adc.ADS1256_SetChannel(0)
            self._channels = cmdDict['args']
        elif cmdDict['cmd'] == 'devices':
            ret = self.enumerate_devices()
            self._qPICO.put({'dev': 'FC', 'cmd': 'devices', 'args': ret})
        elif cmdDict['cmd'] == 'connect':
            self.connect()
            self._qPICO.put({'dev': 'FC', 'cmd': 'connection', 'args': self._flagConnected})
        elif cmdDict['cmd'] == 'disconnect':
            self.disconnect()
            self._qPICO.put({'dev': 'FC', 'cmd': 'connection', 'args': self._flagConnected})

    def fAvg(self):

        return self._fAvg

    def setFreqTarget(self, fTarget):

        return True

    # Connection
    def enumerate_devices(self):
        
        return ['ADS1256']
    
    def connect(self):

        if not self._flagConnected:
            if self.adc.ADS1256_init() == 0:
                self._flagConnected = True
                print('Frequency counter connected!', flush=True)
                return True
            else:
                return False
        else:
            return False

    def disconnect(self):

        if self._flagConnected:
            self._flagConnected = False
            print('Frequency counter disconnected!', flush=True)
            return True
        else:
            return False
    
    def releaseGPIO(self):

        self.adc.ADS1256_ReleaseGPIO()

    # Measurement
    def read_freq(self):

        if self._flagConnected:

            if self._channels == '1':
                f = self.adc.ADS1256_Read_ADC_Data()
                ret = [
                    '{:.15e}'.format(f),
                    '{:.15e}'.format(f)
                ]
            elif self._channels == '2':
                f1 = self.adc.ADS1256_GetChannelValue(0)
                f2 = self.adc.ADS1256_GetChannelValue(0)
                ret = [
                    '{:.15e}'.format(f1),
                    '{:.15e}'.format(f2)
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
                    # self._qPICO.put({'dev': 'FC', 'cmd': 'data', 'args': self._f})
                except ValueError:
                    return False
        
            return True
        else:
            return False

