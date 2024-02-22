# -*- coding: utf-8 -*-

import os
import sys
import time
from datetime import datetime
import threading
import multiprocessing as mp

import yaml

from misc.generators import generate_widgets, generate_layout
from misc.commands import *
from src.handlerStabilization import *
import src.frequency_stability as freq_stab
from src.utils import save_csv

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QFileDialog, QMenuBar
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from widgets.Dialogs import *

import numpy as np


tauMargin = 0.1 # Hz
errorMargin = 5 # Hz or deg
updateTimestep = 5e-3 # s
updateTimestepAllan = 500e-3 # s

availableFilesCfg = '(*.yml *.yaml)'
availableFilesData = '(*.csv)'


def _handleStab(q, conn, eventDisconnect):

    print('Starting stabilization process', flush=True)
    handler = handlerStabilization(q, conn)

    while True:
        start = time.time()
        # check for disconnect
        if eventDisconnect.is_set():
            print('Closing stabilization process')
            break

        # acquire data
        if handler.measure():
            # control only if new data arrived
            handler.filterUpdate()

        # check queue
        while not handler.queueEmpty():
            handler.parseCommand()

        stop = time.time()
        # print(stop - start)
        to_wait = handler.wait(start, stop)
        # if to_wait < 0:
        #     print('[{0}] Delay: {1} s'.format(datetime.now(), to_wait), flush=True)

    handler.disconnect()
    conn.close()


class FrequencyDriftStabilizer(QMainWindow):

    updatePlots = pyqtSignal()
    updatePlotAllan = pyqtSignal()
    updateDevicesFC = pyqtSignal(list)
    updateDevicesDDS = pyqtSignal(list)
    autosave = pyqtSignal()
    phaseLock = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Configuration files
        widgets_conf = self.getWidgetsConfig()
        layout_conf = self.getLayoutConfig()

        # Variables
        self._paramsFC = {}
        self._i = 0 # iterator for measuring loop
        self._N = 1000 # number of points to remember
        self._ts = np.zeros(self._N) # s
        self._val1 = np.zeros(self._N) * np.nan # Hz
        self._val2 = np.zeros(self._N) * np.nan # Hz
        self._valAvg = np.zeros(self._N) * np.nan # Hz
        self._valAvgFilt = np.zeros(self._N) * np.nan # Hz
        self._pv = np.zeros(self._N) * np.nan # Hz
        self._error_Hz = np.zeros(self._N) * np.nan # Hz
        self._error_period = np.zeros(self._N) * np.nan # period
        self._control = np.zeros(self._N) * np.nan # Hz
        self._valTarget = 0

        self._tauN = 20 # number of points for Allan deviation plot
        self._taus = np.zeros(self._tauN)
        self._AllanDevs = np.zeros(self._tauN) * np.nan

        self._iterAutosave = 0
        self._timestampAutosave = np.zeros(self._N)

        self._lowerPlot = 'Error'
        self._mode = 'Frequency'
        self._filterType = 'loop'

        # Flags
        self._flagFCConnected = False
        self._flagDDSConnected = False
        self._flagDDSEnabled = False
        self._flagLockReady = False
        self._flagLocked = False
        self._flagAllan = False
        self._flagAutosave = False

        # Stabilization process
        self._eventDisconnect = mp.Event()
        self._queueStab = mp.Queue()
        # run subprocess
        self._stabConn, child_conn = mp.Pipe()
        self._processStab = mp.Process(target=_handleStab, args=(self._queueStab, child_conn, self._eventDisconnect,))
        self._processStab.start()

        # Update thread
        self._eventStop = threading.Event()
        self._threadUpdate = threading.Thread(target=self._update, args=(self._eventStop, self._stabConn))
        self._threadUpdate.start()

        # Update Allan thread
        self._eventStopAllan = threading.Event()
        self._threadUpdateAllan = threading.Thread(target=self._updateAllan, args=(self._eventStopAllan, ))
        self._threadUpdateAllan.start()

        # Create needed dirs
        if not os.path.exists('./logs'):
            os.makedirs('./logs')
        if not os.path.exists('./data'):
            os.makedirs('./data')

        # GUI
        self.initWidgets(widgets_conf)
        self.initLayout(layout_conf)
        self.createMenu()
        self.initUI()

        time.sleep(1)

        if not self._importParams(True):
            self._getStabilizerSettings() 
        self._getDevicesFC()
        self._getParamsFC()
        self._getDevicesDDS()

        print('Running application')
        self.show()

    def closeEvent(self, event):

        # Close all connections
        # unlock
        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'lock',
            'args': 0
        })
        # disconnect DDS
        self._queueStab.put({
            'dev': 'DDS',
            'cmd': 'disconnect'
        })
        # disconnect FC
        self._queueStab.put({'dev': 'FC', 'cmd': 'disconnect'})

        self._eventStopAllan.set()
        self._threadUpdateAllan.join()
        print('Allan update thread closed!')

        self._eventStop.set()
        self._threadUpdate.join()
        print('Update thread closed!')
        if self._flagAutosave:
            self.autosave.emit()

        self._eventDisconnect.set()
        self._processStab.join()
        self._stabConn.close()
        print('Stabilization process closed!')

        self._exportParams(whileExit=True)
        print('Done!')
        return super().closeEvent(event)
    
    # Widgets and layout
    def getWidgetsConfig(self):

        config_path = os.path.join("./", "config", "widgets_config.yml")
        with open(config_path) as config_file:
            widgets_conf = yaml.safe_load(config_file)

        return widgets_conf

    def getLayoutConfig(self):

        config_path = os.path.join("./", "config", "layout_config.yml")
        with open(config_path) as config_file:
            layout_conf = yaml.safe_load(config_file)

        return layout_conf

    def initWidgets(self, widget_conf):

        print('Initialising widgets...')

        self._widgets = generate_widgets(widget_conf)

        # Additional init of plotFrequency
        self._widgets['plotFrequency'].setLabel("bottom", "Time [s]")
        self._widgets['plotFrequency'].setLabel("left", "Frequency [Hz]" )
        self._curveFreq1 = self._widgets['plotFrequency'].plot(pen='y')
        self._curveFreq2 = self._widgets['plotFrequency'].plot(pen='b')
        self._curvePV = self._widgets['plotFrequency'].plot(pen='r')

        # Additional init of plotStabilizer
        self._widgets['plotStabilizer'].setLabel("bottom", "Time [s]")
        self._widgets['plotStabilizer'].setLabel("left", "Error [Hz]" )
        self._curveError = self._widgets['plotStabilizer'].plot(pen='y')

        # Additional init of plotAllan
        self._widgets['plotAllan'].setLabel("bottom", "Tau [s]")
        self._widgets['plotAllan'].setLabel("left", "Allan deviation")
        self._widgets['plotAllan'].setLogMode(x=False, y=True)
        self._curveAllan = self._widgets['plotAllan'].plot(pen='y')
        # self._widgets['checkAllan'].setChecked(True)

        # Setting combos in settings section
        self._widgets['comboRate'].setCurrentIndex(4)

        # Additional settings of lock led
        self._widgets['ledLock'].off_color_1 = QColor(28, 0, 0)
        self._widgets['ledLock'].off_color_2 = QColor(156, 0, 0)
        self._widgets['ledLock'].setDisabled(True)

        # Additional settings of phase lock led
        self._widgets['ledPhaseLock'].off_color_1 = QColor(28, 0, 0)
        self._widgets['ledPhaseLock'].off_color_2 = QColor(156, 0, 0)
        self._widgets['ledPhaseLock'].setDisabled(True)

        print('Widgets initialised!')

    def initLayout(self, layout_conf):

        print('Initialising layout...')

        mainLayout = generate_layout(layout_conf, self._widgets)

        mainWidget = QWidget()
        mainWidget.setLayout(mainLayout)
        self.setCentralWidget(mainWidget)

        print('Layout initialised!')

    def createMenu(self):

        menuFile = self.menuBar().addMenu('File')
        # Import/export parameters
        actionImportParams = menuFile.addAction("Import parameters")
        actionImportParams.triggered.connect(self._importParams)
        actionExportParams = menuFile.addAction("Export parametes")
        actionExportParams.triggered.connect(self._exportParams)

        menuFile.addSeparator()
        # Save frequency data
        actionSaveFrequencyData = menuFile.addAction("Save data")
        actionSaveFrequencyData.triggered.connect(self._saveData)

    def initUI(self):

        self._widgets['btnFCConnect'].clicked.connect(self._connectFC)
        self._widgets['btnFCRefresh'].clicked.connect(self._getDevicesFC)
        self._widgets['btnDDSConnect'].clicked.connect(self._connectDDS)
        self._widgets['btnDDSRefresh'].clicked.connect(self._getDevicesDDS)
        self._widgets['btnDDSEnable'].clicked.connect(self._enableDDS)
        self._widgets['btnLock'].clicked.connect(self._lock)
        self._widgets['btnResetFilter'].clicked.connect(self._resetFilter)
        self._widgets['btnSetFilter'].clicked.connect(self._setFilter)
        self._widgets['btnResetPlot'].clicked.connect(self._resetVariables)

        self.updatePlots.connect(self._plotFreq)
        self.updatePlotAllan.connect(self._plotAllan)
        self.updateDevicesFC.connect(self._updateDevicesListFC)
        self.updateDevicesDDS.connect(self._updateDevicesListDDS)
        self.autosave.connect(self._autosave)
        self.phaseLock.connect(self._phaseLockChanged)

        self._widgets['comboRate'].currentIndexChanged.connect(self._sendParamsFC)
        self._widgets['comboChannelsFC'].currentIndexChanged.connect(self._sendParamsFC)
        self._widgets['comboMode'].activated.connect(self._modeChanged) # emits only when edited by user
        self._widgets['comboFilterType'].currentIndexChanged.connect(self._filterTypeChanged)
        self._widgets['comboShow'].activated.connect(self._changedLowerPlotShow)

        self._widgets['freqDDS'].editingFinished.connect(self._sendParamsDDS)
        self._widgets['ampDDS'].editingFinished.connect(self._sendParamsDDS)
        self._widgets['phaseDDS'].editingFinished.connect(self._sendParamsDDS)

        self._widgets['valTarget'].editingFinished.connect(self._getStabilizerSettings)
        self._widgets['checkLowpass'].stateChanged.connect(self._applyLowpass)
        self._widgets['filters'].newFilterDesigned.connect(self._setLowpass)

        self._widgets['checkAllan'].stateChanged.connect(self._AllanChanged)

        self._widgets['checkAutosave'].stateChanged.connect(self._enableAutosave)

    # FC connection
    def _getDevicesFC(self):

        self._queueStab.put({'dev': 'FC', 'cmd': 'devices'})

    def _updateDevicesListFC(self, devs):

        self._widgets['comboConnFC'].clear()
        self._widgets['comboConnFC'].addItems(devs)

    def _connectFC(self):

        if not self._flagFCConnected:
            if not self._getParamsFC():
                return False
            address = self._widgets['comboConnFC'].currentText()
            self._queueStab.put({'dev': 'FC', 'cmd': 'connect', 'args': address})
            self._sendParamsFC()
        else:
            self._queueStab.put({'dev': 'FC', 'cmd': 'disconnect'})

        return True

    # FC settings
    def _getParamsFC(self):

        tmp = {}

        try:
            tmp['Rate'] = self._widgets['comboRate'].currentText()
            tmp['Rate value'] = cmds_values['rate'][tmp['Rate']]
            tmp['Frequency sampling [Hz]'] = 1/tmp['Rate value']
            tmp['Channels'] = self._widgets['comboChannelsFC'].currentText()
        except ValueError:
            dialogWarning('Could not read parameters!')
            return False

        self._paramsFC = tmp

        # GUI settings
        self._widgets['filters'].setSampling(tmp['Frequency sampling [Hz]'])
        self._widgets['labelSampling'].setText('Sampling: {:.0f} Hz'.format(tmp['Frequency sampling [Hz]']))

        # update ts
        self._ts = np.arange(0, self._N)*self._paramsFC['Rate value']

        # Allan deviation tau recalculation
        self._AllanDevSettings()

        return True

    def _sendParamsFC(self):
        
        if not self._getParamsFC():
            return False
        
        self._queueStab.put({'dev': 'FC', 'cmd': 'rate', 'args': self._paramsFC['Rate']})
        print('Rate changed to {}'.format(self._paramsFC['Rate']))

        self._queueStab.put({'dev': 'FC', 'cmd': 'channels', 'args': self._paramsFC['Channels']})
        print('Channels changed to {}'.format(self._paramsFC['Channels']))

        self._resetVariables()

    # DDS connection
    def _getDevicesDDS(self):

        self._queueStab.put({'dev': 'DDS', 'cmd': 'devices'})

    def _updateDevicesListDDS(self, devs):

        self._widgets['comboConnDDS'].clear()
        self._widgets['comboConnDDS'].addItems(devs)

    def _connectDDS(self):

        if not self._flagDDSConnected:
            conn = self._widgets['comboConnDDS'].currentText()
            self._queueStab.put({
                'dev': 'DDS',
                'cmd': 'connect',
                'args': conn
            })
        else:
            self._queueStab.put({
                'dev': 'DDS',
                'cmd': 'disconnect'
            })
    
    # DDS settings
    def _sendParamsDDS(self):

        # Frequency
        tmp = {
            'dev': 'DDS',
            'cmd': 'freq'
        }

        try:
            tmp['args'] = float(self._widgets['freqDDS'].text())
        except ValueError:
            dialogWarning('Could not read DDS frequency!')
            return False

        self._queueStab.put(tmp)

        # Amplitude
        tmp = {
            'dev': 'DDS',
            'cmd': 'amp'
        }

        try:
            tmp['args'] = float(self._widgets['ampDDS'].text())
        except ValueError:
            dialogWarning('Could not read DDS amplitude!')
            return False

        self._queueStab.put(tmp)

        # Phase
        tmp = {
            'dev': 'DDS',
            'cmd': 'phase'
        }

        try:
            tmp['args'] = float(self._widgets['phaseDDS'].text())
        except ValueError:
            dialogWarning('Could not read DDS phase!')
            return False

        self._queueStab.put(tmp)

        return True

    def _enableDDS(self):

        if not self._flagDDSConnected:
            dialogWarning('Connect to DDS first!')
            return False

        if not self._flagDDSEnabled:
            self._sendParamsDDS()
            self._queueStab.put({'dev': 'DDS', 'cmd': 'en', 'args': 1})
            self._flagDDSEnabled = True
            self._widgets['btnDDSEnable'].setText('Disable')
        else:
            if self._flagLocked:
                dialogWarning('Disengage lock first!')
                return False
            self._queueStab.put({'dev': 'DDS', 'cmd': 'en', 'args': 0})
            self._flagDDSEnabled = False
            self._widgets['btnDDSEnable'].setText('Enable')

        return True

    # Stabilizer settings
    def _modeChanged(self):

        # Do nothing if no change was made
        if self._widgets['comboMode'].currentText() == self._mode:
            return

        # Disable mode change if locked
        if self._flagLocked:
            idx = (self._widgets['comboMode'].currentIndex() + 1) % 2
            self._widgets['comboMode'].setCurrentIndex(idx)
            dialogWarning('Disable lock before changing mode!')
            return

        self._mode = self._widgets['comboMode'].currentText()
        self._changedLowerPlotShow() # adjust lower plot units
        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'mode',
            'args': self._mode
        })
        self._flagLockReady = False

    def _filterTypeChanged(self):

        tmp = self._widgets['comboFilterType'].currentText()
        if tmp == 'Loop':
            self._filterType = 'loop'
        elif tmp == 'PID':
            self._filterType = 'pid'

    def _resetVariables(self):

        # Reset frequencies
        self._val1 = np.zeros(self._N) * np.nan
        self._val2 = np.zeros(self._N) * np.nan
        self._valAvg = np.zeros(self._N) * np.nan
        self._valAvgFilt = np.zeros(self._N) * np.nan
        # Reset stabilization parameters
        self._pv = np.zeros(self._N) * np.nan
        self._error_Hz = np.zeros(self._N) * np.nan
        self._error_period = np.zeros(self._N) * np.nan
        self._control = np.zeros(self._N) * np.nan
        # Reset Allan deviation
        self._AllanDevs = np.zeros(self._tauN) * np.nan
        # Reset iterators
        self._i = 0
        self._iterAutosave = 0

        return True

    def _setSetpoint(self):

        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'sp',
            'args': self._valTarget
        })

    def _getStabilizerSettings(self):

        try:
            self._valTarget = float(self._widgets['valTarget'].text())
            self._mode = self._widgets['comboMode'].currentText()
        except ValueError:
            dialogWarning('Invalid stabilizer settings!')
            return False

        self._setSetpoint()
        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'mode',
            'args': self._mode
        })
        
        return True

    def _setFilter(self):

        # Frequency
        filterParamsFreq = self._widgets['filters'].filterCoefs('{}-freq'.format(self._filterType))
        if not filterParamsFreq:
            self._flagLockReady = False
            return

        filterParamsFreq['params']['dt'] = self._paramsFC['Rate value']
        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'filt',
            'type': filterParamsFreq['type'],
            'params': filterParamsFreq['params']
        })

        # Phase
        if self._mode == 'Phase':
            filterParamsPhase = self._widgets['filters'].filterCoefs('{}-phase'.format(self._filterType))
            if not filterParamsPhase:
                self._flagLockReady = False
                return

            filterParamsPhase['params']['dt'] = self._paramsFC['Rate value']
            self._queueStab.put({
                'dev': 'filt',
                'cmd': 'filt',
                'type': filterParamsPhase['type'],
                'params': filterParamsPhase['params']
            })

        # Lock ready status
        self._flagLockReady = True
        dialogInformation('Filter set successfully!')

    def _setLowpass(self, lowpassParams):

        if lowpassParams['type'] == 'lowpass':
            self._queueStab.put({
                'dev': 'filt',
                'cmd': 'filt',
                'type': lowpassParams['type'],
                'params': lowpassParams['params']
            })

    def _applyLowpass(self):

        if self._widgets['checkLowpass'].isChecked():
            state = 1
        else:
            state = 0

        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'lpApply',
            'args': state
        })

    def _lock(self):

        if not self._flagLocked:
            if not self._flagLockReady:
                dialogWarning('Set filter first!')
                return False
            elif not self._flagDDSEnabled:
                dialogWarning('Enable DDS first!')
                return False
            else:
                self._setSetpoint()
                self._queueStab.put({
                    'dev': 'filt',
                    'cmd': 'lock',
                    'args': 1
                })

                self._flagLocked = True
                self._widgets['btnLock'].setText('Unlock')
        else:
            self._queueStab.put({
                    'dev': 'filt',
                    'cmd': 'lock',
                    'args': 0
                })

            self._flagLocked = False
            self._widgets['btnLock'].setText('Lock')

        return True

    def _resetFilter(self):

        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'reset'
        })

    def _phaseLockChanged(self, state):

        self._widgets['ledPhaseLock'].setChecked(state)
        if self._lowerPlot == 'Process variable':
            if state:
                self._widgets['plotStabilizer'].setLabel("left", "Process variable [period]")
            else:
                self._widgets['plotStabilizer'].setLabel("left", "Process variable [Hz]")
                            
    # Updating
    def _update(self, eventStop, conn):

        print('Starting update thread')
        flagNewData = False
        while True:
            if eventStop.is_set():
                break

            # Command parsing
            while conn.poll():
                tmp = conn.recv()
                # Frequency counter
                if tmp['dev'] == 'FC':
                    # FC connection
                    if tmp['cmd'] == 'connection':
                        self._flagFCConnected = tmp['args']
                        if self._flagFCConnected:
                            self._widgets['btnFCConnect'].setText('Disconnect')
                        else:
                            self._widgets['btnFCConnect'].setText('Connect')
                    # FC data
                    elif tmp['cmd'] == 'data':
                        flagNewData = True
                        self._val1[self._i] = tmp['args'][0]
                        self._val2[self._i] = tmp['args'][1]
                        self._valAvg[self._i] = np.average(tmp['args'])
                    # FC devices list
                    elif tmp['cmd'] == 'devices':
                        self.updateDevicesFC.emit(tmp['args'])
                # DDS
                elif tmp['dev'] == 'DDS':
                    # DDS connection
                    if tmp['cmd'] == 'connection':
                        self._flagDDSConnected = tmp['args']
                        if self._flagDDSConnected:
                            self._widgets['btnDDSConnect'].setText('Disconnect')
                        else:
                            self._widgets['btnDDSConnect'].setText('Connect')
                            if self._flagLocked:
                                self._lock() # unlock
                            if self._flagDDSEnabled: # software disable DDS
                                self._flagDDSEnabled = False
                                self._widgets['btnDDSEnable'].setText('Enable')
                    # DDS devices list
                    elif tmp['cmd'] == 'devices':
                        self.updateDevicesDDS.emit(tmp['args'])
                # Filter
                elif tmp['dev'] == 'filt':
                    # Filtered/raw average
                    if tmp['cmd'] == 'avg':
                        self._valAvgFilt[self._i] = tmp['args']
                    # Process variable
                    elif tmp['cmd'] == 'pv':
                        self._pv[self._i] = tmp['args']
                        self._error_Hz[self._i] = self._valTarget - self._valAvgFilt[self._i]
                        self._error_period[self._i] = self._error_Hz[self._i]*self._paramsFC['Rate value']
                    # Control
                    elif tmp['cmd'] == 'control':
                        self._control[self._i] = tmp['args']
                    # Mode
                    elif tmp['cmd'] == 'phaseLock':
                        self.phaseLock.emit(tmp['args'])
                else:
                    print('Unknown device! dev: {0} cmd: {1}'.format(tmp['dev'], tmp['cmd']))

            # New data handling
            if flagNewData:
                self.updatePlots.emit()

                # Led lock indicator
                if (np.absolute(self._error_Hz[self._i]) < errorMargin) and self._flagLocked:
                    self._widgets['ledLock'].setChecked(True)
                else:
                    self._widgets['ledLock'].setChecked(False)

                flagNewData = False
                self._i += 1

                # Autosave
                if self._flagAutosave:
                    self._timestampAutosave[self._iterAutosave] = time.time()
                    self._iterAutosave += 1
                if self._iterAutosave == self._N-1:
                    self._iterAutosave = 0
                    self.autosave.emit()

            # Data rolling
            if self._i >= self._N:
                self._i = self._N-1
                self._val1 = np.roll(self._val1, -1)
                self._val1[-1] = np.nan
                self._val2 = np.roll(self._val2, -1)
                self._val2[-1] = np.nan
                self._valAvg = np.roll(self._valAvg, -1)
                self._valAvg[-1] = np.nan
                self._valAvgFilt = np.roll(self._valAvg, -1)
                self._valAvgFilt[-1] = np.nan
                self._pv = np.roll(self._pv, -1)
                self._pv[-1] = np.nan
                self._error_Hz = np.roll(self._error_Hz, -1)
                self._error_Hz[-1] = np.nan
                self._error_period = np.roll(self._error_period, -1)
                self._error_period[-1] = np.nan
                self._control = np.roll(self._control, -1)
                self._control[-1] = np.nan

            time.sleep(updateTimestep)
        print('Closing update thread')

    # Allan deviation
    def _AllanChanged(self):

        if self._widgets['checkAllan'].isChecked():
            self._flagAllan = True
        else:
            self._flagAllan = False
            self._AllanDevs = np.zeros(self._tauN) * np.nan
            self._plotAllan()

    def _AllanDevSettings(self):

        tauMin = 1 / (self._paramsFC['Frequency sampling [Hz]'] - tauMargin)
        tauMax = self._N / 2 / (self._paramsFC['Frequency sampling [Hz]'] + tauMargin)

        self._taus = np.linspace(tauMin, tauMax, self._tauN)

        return True

    def _calcAllanDeviation(self):

        if self._i < 1:
            return False

        tauMaxCurrent = (self._i+1) / 2 / (self._paramsFC['Frequency sampling [Hz]'] + tauMargin)
        n = 0
        for tau in self._taus:
            if tau <= tauMaxCurrent:
                n += 1
            else:
                break

        fs = self._valAvg[~np.isnan(self._valAvg)]
        fs_frac = freq_stab.calc_fractional_frequency(
            fs,
            self._valTarget
        )
        phase_error = freq_stab.calc_phase_error(
            fs_frac,
            self._paramsFC['Frequency sampling [Hz]']
        )
        # print(phase_error)
        for i in range(n):
            self._AllanDevs[i] = freq_stab.calc_ADEV_overlapped_single(
                phase_error,
                self._taus[i],
                self._paramsFC['Frequency sampling [Hz]']
            )
        # print(self._taus, self._AllanDevs)

    def _updateAllan(self, eventStop):

        print('Starting Allan update thread')
        while True:
            if eventStop.is_set():
                break

            if self._flagAllan:
                try:
                    self._calcAllanDeviation()
                except Exception as e:
                    print('Could not calculate allan deviation! ', e, flush=True)
                self.updatePlotAllan.emit()

            time.sleep(updateTimestepAllan)
        
        print('Closing Allan update thread')

    # Plotting
    def _changedLowerPlotShow(self):

        self._lowerPlot = self._widgets['comboShow'].currentText()

        if self._mode == 'Phase':
            unit = 'period'
        else:
            unit = 'Hz'

        if self._lowerPlot == 'Error [Hz]':
            self._widgets['plotStabilizer'].setLabel("left", "Error [Hz]" )
        elif self._lowerPlot == 'Error [period]':
            self._widgets['plotStabilizer'].setLabel("left", "Error [period]" )
        elif self._lowerPlot == 'Process variable':
            self._widgets['plotStabilizer'].setLabel("left", "Process variable [{}]".format(unit))
        elif self._lowerPlot == 'Control':
            self._widgets['plotStabilizer'].setLabel("left", "Control [Hz]" )

    def _plotFreq(self):

        # Frequency plot
        self._curveFreq1.setData(self._ts[:self._i], self._val1[:self._i])
        self._curveFreq2.setData(self._ts[:self._i], self._val2[:self._i])
        self._curvePV.setData(self._ts[:self._i], self._valAvgFilt[:self._i])

        # Error and control plot
        if self._lowerPlot == 'Error [Hz]':
            self._curveError.setData(self._ts[:self._i], self._error_Hz[:self._i])
        elif self._lowerPlot == 'Error [period]':
            self._curveError.setData(self._ts[:self._i], self._error_period[:self._i])
        elif self._lowerPlot == 'Process variable':
            self._curveError.setData(self._ts[:self._i], self._pv[:self._i])
        elif self._lowerPlot == 'Control':
            self._curveError.setData(self._ts[:self._i], self._control[:self._i])

    def _plotAllan(self):

        self._curveAllan.setData(self._taus, self._AllanDevs)

    # File menu actions
    def _exportParams(self, whileExit=False):

        # GUI parameters
        params = {
            'Rate': self._widgets['comboRate'].currentText(),
            'Rate index': self._widgets['comboRate'].currentIndex(),
            'FC channels': self._widgets['comboChannelsFC'].currentText(),
            'FC channels index': self._widgets['comboChannelsFC'].currentIndex(),
            'Filter type': self._widgets['comboFilterType'].currentText(),
            'Filter type index': self._widgets['comboFilterType'].currentIndex(),
            'Mode': self._widgets['comboMode'].currentText(),
            'Mode index': self._widgets['comboMode'].currentIndex(),
            'DDS frequency [Hz]': float(self._widgets['freqDDS'].text()),
            'DDS amplitude [%]': float(self._widgets['ampDDS'].text()),
            'DDS phase [deg]': float(self._widgets['phaseDDS'].text()),
            'Lowpass active': self._widgets['checkLowpass'].isChecked()
        }

        params['Target frequency [Hz]'] = float(self._widgets['valTarget'].text())

        # Filters parameters
        paramsFilters = self._widgets['filters'].getParams()
        params['Filters'] = paramsFilters
        # Used devices
        config_path = os.path.join("./", "config", "devices.yml")
        with open(config_path) as config_file:
            devices_config = yaml.safe_load(config_file)
        params['Devices'] = devices_config

        if whileExit:
            outputPath = './logs/last_settings.yml'
        else:
            outputPath = QFileDialog.getSaveFileName(
                self,
                'Save file',
                '~/',
                availableFilesCfg
            )[0]
        if outputPath == '':
            return False

        with open('{}'.format(outputPath), 'w') as f:
            yaml.dump(params, f)
        print('Parameters exported to {}'.format(outputPath), flush=True)
        if not whileExit:
            dialogInformation('Parameters exported succesfully!')
        return True

    def _importParams(self, whileInit=False):

        if whileInit:
            inputPath = './logs/last_settings.yml'
        else:
            inputPath = QFileDialog.getOpenFileNames(
                self,
                'Open file',
                '~/',
                availableFilesCfg
            )[0]

            if len(inputPath) > 1:
                dialogWarning('Choose only one file!')
                return False
            elif len(inputPath) == 0:
                return False
            inputPath = inputPath[0]

        # Import params
        try:
            with open(inputPath) as f:
                params = yaml.safe_load(f)
        except Exception as e:
            if whileInit:
                return False
            else:
                dialogWarning('Could not import parameters! {}'.format(e))

        try:
            # Set frequency counter params
            self._widgets['comboRate'].setCurrentIndex(params['Rate index'])
            self._widgets['comboChannelsFC'].setCurrentIndex(params['FC channels index'])
            # Set DDS params
            self._widgets['freqDDS'].setText('{:.9e}'.format(params['DDS frequency [Hz]']))
            self._widgets['ampDDS'].setText('{}'.format(params['DDS amplitude [%]']))
            self._widgets['phaseDDS'].setText('{}'.format(params['DDS phase [deg]']))
            # Set stabilization params
            self._widgets['comboFilterType'].setCurrentIndex(params['Filter type index'])
            self._filterTypeChanged()
            self._widgets['comboMode'].setCurrentIndex(params['Mode index'])
            self._mode = self._widgets['comboMode'].currentText()
            self._widgets['valTarget'].setText('{:.9e}'.format(params['Target frequency [Hz]']))
            self._widgets['checkLowpass'].setChecked(params['Lowpass active'])
            # Set filter params
            self._widgets['filters'].setParams(params['Filters'])
        except KeyError as e:
            print('Import parameters failed! {}'.format(e))

        self._getStabilizerSettings()
        self._changedLowerPlotShow()

        print('Parameters imported from {}'.format(inputPath))
        if not whileInit:
            dialogInformation('Parameters imported succesfully!')
        return True

    def _prepareData(self, timestamp=False):

        if self._mode == 'Phase':
            unit = 'period'
        else:
            unit = 'Hz'

        data = {
            'Time [s]': self._ts[:self._i],
            'Frequency 1 [Hz]': self._val1[:self._i],
            'Frequency 2 [Hz]': self._val2[:self._i],
            'Frequency avg [Hz]': self._valAvg[:self._i],
            'Process variable [{}]'.format(unit): self._pv[:self._i],
            'Error [Hz]': self._error_Hz[:self._i],
            'Error [period]': self._error_period[:self._i],
            'Control [Hz]': self._control[:self._i]
        }
        if timestamp:
            data['Timestamp [s]'] = self._timestampAutosave[:self._i]

        meta = {
            'Mode': self._widgets['comboMode'].currentText(),
            'Target frequency [Hz]': self._widgets['valTarget'].text(),
            'Rate [s]': self._paramsFC['Rate value']
        }

        return data, meta

    def _saveData(self):

        outputPath = QFileDialog.getSaveFileName(
                self,
                'Save file',
                '~/',
                availableFilesData
            )[0]
        if outputPath == '':
            return False
        if not outputPath.endswith('.csv'):
            outputPath += '.csv'

        data, meta = self._prepareData()
        save_csv(
            data,
            outputPath,
            meta,
            index=False
        )

        print('{0} data saved to {1}'.format(valName, outputPath))
        dialogInformation('{0} data saved to {1}'.format(valName, outputPath))
        return True

    # Autosave
    def _enableAutosave(self):

        if self._widgets['checkAutosave'].isChecked():
            if not self._flagFCConnected:
                self._widgets['checkAutosave'].setChecked(0)
                dialogWarning('Connect frequency counter first!')
                return
            if not self._flagAutosave:
                self._iterAutosave = 0
                self._flagAutosave = True
                dialogInformation('Autosave turned on!')
        else:
            if self._flagAutosave:
                self._flagAutosave = False
                self.autosave.emit()

    def _autosave(self):

        data, meta = self._prepareData(True)
        path = './data/autosave_{}.csv'.format(time.time())

        save_csv(
            data,
            path,
            meta,
            index=False
        )

        print('[{0}] Autosave'.format(datetime.now()))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = FrequencyDriftStabilizer()
    sys.exit(app.exec_())
