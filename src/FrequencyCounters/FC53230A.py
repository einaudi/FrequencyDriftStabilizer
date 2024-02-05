# -*- coding: utf-8 -*-
'''Module for Keysight devices support

DM34461A - Digital Multimeter 34461A

Values can be standard floats eg. 0.002 or scientific notation eg. 2e-3
Units are Hz, s, V, degrees by default unless noted otherwise
'''


import time

import pyvisa
import numpy as np

from misc.commands import cmds_values


RESOLUTION = 20e-3 # Hz 

class FC53230A():

    def __init__(self, conn):

        self._conn = conn

        self._rm = pyvisa.ResourceManager('@py')
        self._dev = None
        self._flagConnected = False

        self._rate = 0.1
        self._mode = 'Frequency'

        self._f = [0, 0]
        self._fAvg = 0
        self._fTarget = 1e6

        print('FC53230 Frequency Counter handler initiated!')

    def parseCommand(self, cmdDict):
        
        if cmdDict['cmd'] == 'mode':
            self._changeMode(cmdDict['args']) 
        elif cmdDict['cmd'] == 'devices':
            ret = self.list_resources()
            self._conn.send({'dev': 'FC', 'cmd': 'devices', 'args': ret})
        elif cmdDict['cmd'] == 'connect':
            self.connect(cmdDict['args'])
            self._conn.send({'dev': 'FC', 'cmd': 'connection', 'args': self._flagConnected})
        elif cmdDict['cmd'] == 'disconnect':
            self.disconnect()
            self._conn.send({'dev': 'FC', 'cmd': 'connection', 'args': self._flagConnected})
    
    def setFreqTarget(self, fTarget):

        self._fTarget = fTarget
        print('New target frequency: {:.6e} Hz'.format(self._fTarget))

        if self._flagConnected:
            self._dev.write(
                'CONF:FREQ {0}, {1}'.format(
                    self._fTarget,
                    RESOLUTION
                )
            )
            gateTime = self.readGate()
            print('Gate time: {} s'.format(gateTime))

        return True

    # Connection
    def connect(self, conn):

        self._dev = self._rm.open_resource(conn)
        if self._dev is None:
            print('Could not connect to Frequency Counter!', flush=True)
            return False
        else:
            self._flagConnected = True
            print('Frequency Counter connected!', flush=True)

            self._dev.write('ABOR')
            self._dev.write('*RST')
            time.sleep(1)
            # self._dev.write('DISP:STAT 0')

            # self._dev.timeout = None

            self._dev.write('SAMP:COUN 1') # sample count 1
            # self._dev.write('TRIG:COUN 1') # trigger count 1
            # self._dev.write('SENS:FREQ:GATE:SOUR TIME') # gate source time
            # self._dev.write('SENS:FREQ:MODE CONT')
            # self._dev.write('INIT')
            if self._mode == 'phase':
                self._dev.write('FORM:PHAS CENT')

        return True

    def disconnect(self):

        if self._flagConnected:
            self._dev.write('DISP:STAT 1')
            self._dev.close()
            print('Frequency Counter disconnected!', flush=True)
            self._flagConnected = False
            return True
        print('Frequency Counter already disconnected!')
        return True

    def list_resources(self):

        ret = [item for item in self._rm.list_resources()]
        ret.append('TCPIP0::172.17.32.151::INSTR')

        return ret

    # Settings
    def _changeMode(self, mode):

        if mode == 'Phase':
            self._mode = 'phase'
            if  self._flagConnected:
                self.initPhaseReadout()
                self._dev.query('FETC?')
                self._dev.write('FORM:PHAS CENT')
        else: # includes mode == 'Frequency'
            self._mode = 'frequency'
            if  self._flagConnected:
                self.initFrequencyReadout()
                self._dev.query('FETC?')

    def setGate(self, gateTime):

        self._rate = gateTime
        if self._flagConnected:
            self._dev.write('FREQ:GATE:TIME {0}'.format(self._rate))

    def initFrequencyReadout(self, ch=1):

        self._dev.write(
            'CONF:FREQ {0}, {1}, (@{2})'.format(
                self._fTarget,
                RESOLUTION,
                ch
            )
        )
        self._dev.write('INIT')

    def initPhaseReadout(self):

        # self._dev.write('CONF:PHAS (@1),(@2)') # 1 -> 2
        self._dev.write('CONF:PHAS (@2),(@1)') # 2 -> 1
        self._dev.write('INIT')

    # Readout
    def readCounts(self):

        ret = self._dev.query('DATA:POIN?')

        return int(ret)
    
    def readGate(self):

        if not self._flagConnected:
            return 0

        ret = self._dev.query('SENS:FREQ:GATE:TIME?')

        return float(ret)

    def readFrequency(self):

        if not self._flagConnected:
            return 0

        # Using fetch
        self._dev.write('INIT')
        ret = self._dev.query('FETC?')

        # Using data last
        # ret = self._dev.query('DATA:LAST?')

        # Using MEASURE:FREQ command
        # ret = self._dev.query(
        #     'MEAS:FREQ? {0}, {1}, (@1)'.format(
        #         self._fTarget,
        #         RESOLUTION
        #     )
        # )

        return ret

    def measure(self, ch=1):

        if not self._flagConnected:
            return False

        # Using MEASURE:FREQUENCY
        # self._f[0] = float(self._dev.query(
        #     'MEAS:FREQ? {0}, {1}, (@1)'.format(
        #         self._fTarget,
        #         RESOLUTION
        #     )
        # ))
        # self._f[1] = float(self._dev.query(
        #     'MEAS:FREQ? {0}, {1}, (@2)'.format(
        #         self._fTarget,
        #         RESOLUTION
        #     )
        # ))
        # Using FETCH
        if self._mode == 'frequency':
            self.initFrequencyReadout(1)
            self._f[0] = float(self._dev.query('FETC?'))
            self.initFrequencyReadout(2)
            self._f[1] = float(self._dev.query('FETC?'))
        elif self._mode == 'phase':
            self.initPhaseReadout()
            d = float(self._dev.query('FETC?'))
            self._f[0] = d
            self._f[1] = d

        self._fAvg = np.average(self._f)
        self._conn.send({'dev': 'FC', 'cmd': 'data', 'args': self._f})

    def fAvg(self):

        return self._fAvg

    # Misc
    def loop_until_counts_acq(self):

        cts = int(self._dev.query('SAMP:COUN?')) * int(self._dev.query('TRIG:COUN?'))
        tmp = 0

        while(tmp < cts):
            time.sleep(0.1)
            tmp = self.read_counts()

        return True


if __name__ == '__main__':

    import time
    from src.handlerStabilization import DummyConnection

    ip = '172.17.32.151'

    fc = FC53230A(DummyConnection())
    fc.connect('TCPIP0::{0}::INSTR'.format(ip))
    fc.setFreqTarget(10e6)

    # Check gatetime settings
    # for gateTime, gateTimeValue in cmds_values['rate'].items():
    #     fc.setGate(gateTimeValue)
    #     tmp = fc.readGate()

    #     print('{0}\t{1}\t{2}'.format(gateTime, gateTimeValue, tmp))

    # Read frequency
    # rate = 0.01
    # fc.initFrequencyReadout()
    # for i in range(10):
    #     start = time.time()
    #     tmp = fc.readFrequency().strip()
    #     stop = time.time()
    #     to_wait = rate - (stop - start)
    #     if to_wait < 0:
    #         pass
    #     else:
    #         time.sleep(to_wait)
    #     stop = time.time()
    #     print(tmp, stop-start)

    # Measure both frequencies
    rate = 0.01
    print('Gate time: ', fc.readGate())
    for i in range(10):
        start = time.time()
        fc.measure()
        stop = time.time()
        to_wait = rate - (stop - start)
        if to_wait < 0:
            pass
        else:
            time.sleep(to_wait)
        stop = time.time()
        print('{0:.2e}, {1:.2e}'.format(*fc._f), stop-start)
    
    fc.disconnect()