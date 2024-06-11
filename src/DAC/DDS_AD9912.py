# -*- coding: utf-8 -*-

from src.DAC.AD9912_lib.AD9912 import AD9912


class AD9912Handler():

    def __init__(self, conn):

        self._qPICO = conn

        self.dds = AD9912()
        self._freq = 0
        self._amp = 20

        self._flagConnected = False
        self._flagEnabled = False

        print('DAC8532 handler initiated!', flush=True)

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
                self._enable(params['args'])
        # Frequency
        elif params['cmd'] == 'freq':
            self.setFreq(params['args'])
            self._freq = params['args']
        # Amplitude
        elif params['cmd'] == 'amp':
            self.setAmp(params['args'])
            self._amp = params['args']
        # Phase
        elif params['cmd'] == 'phase':
            self.setPhase(params['args'])

    # Connection
    def enumerate_devices(self):

        devs = ['AD9912']

        # devs.append('USER ADDRESS')

        return devs

    def connect(self):

        if not self._flagConnected:
            print('Connecting to AD9912')
            self._qPICO.put({'dev': 'DAC', 'cmd': 'connection', 'args': 1})
            self._flagConnected = True
            print('DAC connected!', flush=True)
            return True

        print('DDS already connected!')
        return True

    def disconnect(self, disable=True):

        if self._flagConnected:
            # if disable:
            #     self._enable(0)
            self._flagEnabled = False
            self._flagConnected = False
            self._qPICO.put({'dev': 'DAC', 'cmd': 'connection', 'args': 0})
            print('DDS disconnected!', flush=True)

    def _enable(self, state):

        if self._flagConnected:
            if state:
                self._flagEnabled = True
                self.setAmp(self._amp)
                self.setFreq(self._freq)
            else:
                self.setFreq(0)
                self._flagEnabled = False

    # Generator settings
    def setFreq(self, freq):

        if self._flagConnected and self._flagEnabled:
            if freq > 400:
                freq = 400
            if freq < 0:
                freq = 0

            self.dds.setFrequency(freq)

    def setPhase(self, phase):

        return

    def setAmp(self, amp):

        if self._flagConnected and self._flagEnabled:
            if amp > 100:
                amp = 100
            if amp < 0:
                amp = 0

                self.dds.setAmp(amp)


if __name__ == '__main__':

    import time
    from src.handlerStabilization import DummyConnection

    afg = AD9912(DummyConnection())
    afg.connect()
    afg.parseCommand({'cmd': 'en', 'args': 1})

    afg.setFreq(100e6)
    afg.setAmp(100)

    time.sleep(5)

    afg.disconnect()
