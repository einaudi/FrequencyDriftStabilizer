# -*- coding: utf-8 -*-

tauMargin = 0.1 # Hz
errorMargin = 5 # Hz
updateTimestep = 20e-3 # s
updateTimestepAllan = 5e-1 # s

waitOffset = 0.001 # s
phaseLockMargin = 100 # Hz
phaseLockCounterLimit = 200

'''
available filters:
    'pid'
    'IntLowpass'
    'DoubleIntLowpass'
    'DoubleIntDoubleLowpass'
'''
loopFilter = 'DoubleIntDoubleLowpass'
# loopFilter = 'IntLowpass'

flagPrintFilterOutput = True