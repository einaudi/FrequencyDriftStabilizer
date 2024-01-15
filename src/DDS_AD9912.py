# -*- coding: utf-8 -*-

import telnetlib


class AD9912Handler():

    def __init__(self, conn):

        self._conn = conn

        self._DDS = telnetlib.Telnet()

        self._flagConnected = False
        self._flagEnabled = False

        print('AD9912 DDS handler initiated!', flush=True)

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
                    self.setFreq(0)
        # Amplitude
        elif params['cmd'] == 'amp':
            self.setAmp(params['args'])

    def connect(self, ip):

        if not self._flagConnected:
            try:
                self._DDS.open(ip, 22, timeout=5)
                self._flagConnected = True
                print('DDS connected!', flush=True)
                self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 1})
                return True
            except Exception as e:
                self._flagConnected = False
                print('Could not connect to DDS! {}'.format(e), flush=True)
                self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 0})
                return False

        print('DDS already connected!')
        return True

    def disconnect(self, disable=True):

        if self._flagConnected:
            if disable:
                self.setFreq(0)
            self._flagEnabled = False
            self._DDS.close()
            self._flagConnected = False
            self._conn.send({'dev': 'DDS', 'cmd': 'connection', 'args': 0})
            print('DDS disconnected!', flush=True)

    def setFreq(self, freq):

        if self._flagConnected:
            if self._flagEnabled:
                if freq > 400e6:
                    freq = 400e6
                cmd = 'DDS:FREQ {}\n'.format(freq*1e-6)
                print(cmd)
            else:
                cmd = 'DDS:FREQ 0\n'

            try:
                self._DDS.write(cmd.encode('UTF-8'))
            except BrokenPipeError as e:
                print('Could not write to DDS! {}'.format(e))
                self.disconnect(disable=False)
            except Exception as e:
                print('Could not write to DDS! {}'.format(e))

    def setAmp(self, amp):

        if self._flagConnected:
            amp = 0.22*amp + 9 # normalisation to 100%
            cmd = 'DDS:AMP {}\n'.format(amp)
            self._DDS.write(cmd.encode('UTF-8'))



if __name__ == '__main__':

    import time

    class DummyConnection():
        def __init__(self):
            return 
        def send(self, cmd):
            return True

    dds = AD9912Handler(DummyConnection())
    dds.connect('172.17.32.130')
    dds.parseCommand({'cmd': 'en', 'args': 1})

    dds.setFreq(100e6)
    dds.setAmp(100)

    time.sleep(5)

    dds.disconnect()