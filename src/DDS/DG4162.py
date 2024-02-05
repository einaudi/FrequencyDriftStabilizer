# -*- coding: utf-8 -*-

import pyvisa


class DG4162Handler():

    def __init__(self, conn):

        self._conn = conn

        self._rm = pyvisa.ResourceManager('@py')

        self._dev = None
        self._ch = 2 # channel used

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

        # DDS connection
        if params['cmd'] == 'connect':
            self.connect(params['args'])
        elif params['cmd'] == 'disconnect':
            self.disconnect()
        # DDS enable
        elif params['cmd'] == 'en':
            if self._flagConnected:
                self._enable(params['args'])
        # Amplitude
        elif params['cmd'] == 'amp':
            self.setAmp(params['args'])
        # Phase
        elif params['cmd'] == 'phase':
            self.setPhase(params['args'])

    def connect(self, ip):

        conn = 'TCPIP0::{}::INSTR'.format(ip)

        if not self._flagConnected:
            try:
                self._dev = self._rm.open_resource(conn)
                if self._dev is None:
                    print('Could not connect to generator!', flush=True)
                    self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 0})
                    return False
                else:
                    self._flagConnected = True
                    print('Generator connected!', flush=True)
                    self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 1})
                    # Offset to 0
                    self._dev.write("SOUR{0}:VOLT:OFFS {1}".format(self._ch, 0))
                    return True
            except Exception as e:
                self._flagConnected = False
                print('Could not connect to generator! {}'.format(e), flush=True)
                self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 0})
                return False

        print('Generator already connected!')
        return True

    def disconnect(self, disable=True):

        if self._flagConnected:
            if disable:
                self._enable(0)
            self._flagEnabled = False
            self._dev.close()
            self._flagConnected = False
            self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 0})
            print('Generator disconnected!', flush=True)

    def _enable(self, state):

        if self._flagConnected:
            if state:
                self._flagEnabled = True
                self.setOutput(1)
                # self._dev.write('DISP 0')
            else:
                self._flagEnabled = False
                self.setOutput(0)
                self._dev.write('DISP 1')

    def setFreq(self, freq):

        if self._flagConnected:
            if freq > 160e6:
                freq = 160e6
            if freq < 1:
                freq = 1

            try:
                self._dev.write("SOUR{0}:FREQ {1}".format(
                    self._ch,
                    freq
                ))
            except Exception as e:
                print('Could not set frequency! {}'.format(e), flush=True)

    def setPhase(self, phase):

        if self._flagConnected:
            if phase < 0:
                phase = 0
            if phase > 360:
                phase = 360

            try:
                self._dev.write("SOUR{0}:PHAS {1}".format(
                    self._ch,
                    phase
                ))
            except Exception as e:
                print('Could not set phase! {}'.format(e), flush=True)

    def setAmp(self, amp):

        if self._flagConnected:
            amp = 0.01*amp # normalisation to 100%
            self._dev.write("SOUR{0}:VOLT {1}".format(
                self._ch,
                amp
            ))

    # Generator settings
    def setOutput(self, state=0):
        '''
        Set output state of given channel
        
        Args:
            state: output state
        '''
        if state:
            stateToWrite = 1
        else:
            stateToWrite = 0

        self._dev.write("OUTP{0} {1}".format(
            self._ch,
            stateToWrite
        ))


if __name__ == '__main__':

    import time
    from src.handlerStabilization import DummyConnection

    afg = DG4162Handler(DummyConnection())
    afg.connect('172.17.32.183')
    afg.parseCommand({'cmd': 'en', 'args': 1})

    afg.setFreq(100e6)
    afg.setAmp(100)

    time.sleep(5)

    afg.disconnect()