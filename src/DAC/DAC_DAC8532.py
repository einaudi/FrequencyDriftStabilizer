# -*- coding: utf-8 -*-

from src.DAC.DAC8532_lib.DAC8532 import DAC8532


class DAC8532Handler():

    def __init__(self, conn):

        self._qPICO = conn

        self.channel = 0x30 # channel A
        # self.channel = 0x34  # channel B
        self.dac = DAC8532()

        self._flagConnected = False
        self._flagEnabled = False

        print('DG4162 generator handler initiated!', flush=True)

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
        # Amplitude
        elif params['cmd'] == 'amp':
            self.setAmp(params['args'])
        # Phase
        elif params['cmd'] == 'phase':
            self.setPhase(params['args'])

    # Connection
    def enumerate_devices(self):

        devs = ['DAC8532']

        # devs.append('USER ADDRESS')

        return devs

    def connect(self):

        if not self._flagConnected:
            print('Connecting to DAC8532')
            self._qPICO.put({'dev': 'DAC', 'cmd': 'connection', 'args': 1})
            self._flagConnected = True
            print('DAC connected!', flush=True)
            return True

        print('DAC already connected!')
        return True

    def disconnect(self, disable=True):

        if self._flagConnected:
            # if disable:
            #     self._enable(0)
            self._flagEnabled = False
            self._flagConnected = False
            self._qPICO.put({'dev': 'DAC', 'cmd': 'connection', 'args': 0})
            print('Generator disconnected!', flush=True)

    def _enable(self, state):

        if self._flagConnected:
            if state:
                self._flagEnabled = True
            else:
                self._flagEnabled = False

    # Generator settings
    def setFreq(self, freq):

        if self._flagConnected:
            if freq > 2.5:
                freq = 2.5
            if freq < 0:
                freq = 0

            self.dac.DAC8532_Out_Voltage(self.channel, freq)

    def setPhase(self, phase):

        return

    def setAmp(self, amp):

        return


if __name__ == '__main__':

    import time
    from src.handlerStabilization import DummyConnection

    afg = DAC8532Handler(DummyConnection())
    afg.connect('172.17.32.183')
    afg.parseCommand({'cmd': 'en', 'args': 1})

    afg.setFreq(100e6)
    afg.setAmp(100)

    time.sleep(5)

    afg.disconnect()
