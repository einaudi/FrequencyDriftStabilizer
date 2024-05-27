# -*- coding: utf-8 -*-

Npoints = 1000
tauMargin = 0.1 # Hz
errorMargin = 0.003 # Hz
updateTimestep = 20e-3 # s
updateTimestepPlots = 100e-3 # s
updateTimestepAllan = 5e-1 # s

waitOffset = 0.001 # s
phaseLockMargin = 100 # Hz
phaseLockCounterLimit = 200

'''
available filters:
    'pid'
    'IntLowpass' - Single integrator and lowpass
    'DoubleIntLowpass' - Double integrator and lowpass
    'DoubleIntDoubleLowpass' - Double integrator and double lowpass
'''
loopFilter = 'DoubleIntDoubleLowpass'
# loopFilter = 'DoubleIntLowpass'
# loopFilter = 'IntLowpass'

flagPrintFilterOutput = False
