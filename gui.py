# -*- coding: utf-8 -*-

import os
import sys
import time
from datetime import datetime
import threading
import multiprocessing as mp

import yaml

from misc.generators import generate_widgets, generate_layout
from misc.rate import rate_values
from src.handlerStabilization import *
import src.frequency_stability as freq_stab
from src.utils import save_csv
import config.config as cfg

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QFileDialog, QMenuBar
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from widgets.Dialogs import *

import numpy as np

availableFilesCfg = '(*.yml *.yaml)'
availableFilesData = '(*.csv)'


def _handleStab(qPOCI, qPICO, eventDisconnect):

    print('Starting stabilization process', flush=True)
    handler = handlerStabilization(qPOCI, qPICO)

    while True:
        # start = time.time()
        # check for disconnect
        if eventDisconnect.is_set():
            print('Closing stabilization process')
            break

        # acquire data
        if handler.measure():
            # control only if new data arrived
            handler.filterUpdate()
            pass

        # check queue
        while not handler.queueEmpty():
            handler.parseCommand()
        
        # send daata
        handler.sendData()

        # stop = time.time()
        # print(stop - start)
        # to_wait = handler.wait(start, stop)
        # if to_wait < 0:
        #     print('[{0}] Delay: {1} s'.format(datetime.now(), to_wait), flush=True)

    handler.disconnect()


class FrequencyDriftStabilizer(QMainWindow):

    updatePlots = pyqtSignal()
    updatePlotAllan = pyqtSignal()
    autosave = pyqtSignal()

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Configuration files
        widgets_conf = self.getWidgetsConfig()
        layout_conf = self.getLayoutConfig()

        # Variables
        self._paramsADC = {}
        self._i = 0 # iterator for measuring loop
        self._N = 1000 # number of points to remember
        self._ts = np.zeros(self._N) # s
        self._val1 = np.zeros(self._N) * np.nan # Hz
        self._val2 = np.zeros(self._N) * np.nan # Hz
        self._valAvg = np.zeros(self._N) * np.nan # Hz
        self._pv = np.zeros(self._N) * np.nan # Hz
        self._error_Hz = np.zeros(self._N) * np.nan # Hz
        self._control = np.zeros(self._N) * np.nan # Hz
        self._valTarget = 0

        self._tauN = 20 # number of points for Allan deviation plot
        self._taus = np.zeros(self._tauN)
        self._AllanDevs = np.zeros(self._tauN) * np.nan

        self._iterAutosave = 0
        self._timestampAutosave = np.zeros(self._N)

        self._lowerPlot = 'Error'

        # Flags
        self._flagADCConnected = False
        self._flagDACConnected = False
        self._flagDACEnabled = False
        self._flagLockReady = False
        self._flagLocked = False
        self._flagAllan = False
        self._flagAutosave = False

        # Stabilization process
        self._eventDisconnect = mp.Event()
        self._qPOCI = mp.SimpleQueue() # Parent Output Child Input
        self._qPICO = mp.SimpleQueue() # Parent Input Child Output
        # run subprocess
        self._processStab = mp.Process(target=_handleStab, args=(self._qPOCI, self._qPICO, self._eventDisconnect,))
        self._processStab.start()

        # Update thread
        self._eventStop = threading.Event()
        self._threadUpdate = threading.Thread(target=self._update, args=(self._eventStop, self._qPICO))
        self._threadUpdate.start()

        # Update plots
        self._timestampUpdatePlots = time.time()

        # Update Allan
        self._timestampUpdateAllan = time.time()

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
        self._getParamsADC()

        print('Running application')
        self.show()

    def closeEvent(self, event):

        # Close all connections
        # unlock
        self._qPOCI.put({
            'dev': 'filt',
            'cmd': 'lock',
            'args': 0
        })
        # disconnect DAC
        self._qPOCI.put({
            'dev': 'DAC',
            'cmd': 'disconnect'
        })
        # disconnect ADC
        self._qPOCI.put({
            'dev': 'ADC',
            'cmd': 'disconnect'
        })

        self._eventStop.set()
        self._threadUpdate.join()
        print('Update thread closed!')
        if self._flagAutosave:
            self.autosave.emit()

        self._eventDisconnect.set()
        self._processStab.join()
        self._qPOCI.close()
        self._qPICO.close()
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

        # Setting rate combo
        self._widgets['comboRate'].addItems(rate_values.keys())
        self._widgets['comboRate'].setCurrentIndex(4)

        # Additional settings of lock led
        self._widgets['ledLock'].off_color_1 = QColor(28, 0, 0)
        self._widgets['ledLock'].off_color_2 = QColor(156, 0, 0)
        self._widgets['ledLock'].setDisabled(True)

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

        self._widgets['btnADCConnect'].clicked.connect(self._connectADC)
        self._widgets['btnDACConnect'].clicked.connect(self._connectDAC)
        self._widgets['btnDACEnable'].clicked.connect(self._enableDAC)
        self._widgets['btnLock'].clicked.connect(self._lock)
        self._widgets['btnResetFilter'].clicked.connect(self._resetFilter)
        self._widgets['btnSetFilter'].clicked.connect(self._setFilter)
        self._widgets['btnResetPlot'].clicked.connect(self._resetVariables)

        self.updatePlots.connect(self._plotFreq)
        self.updatePlotAllan.connect(self._plotAllan)
        self.autosave.connect(self._autosave)

        self._widgets['comboRate'].currentIndexChanged.connect(self._sendParamsADC)
        self._widgets['comboChannelsADC'].currentIndexChanged.connect(self._sendParamsADC)
        self._widgets['comboShow'].activated.connect(self._changedLowerPlotShow)

        self._widgets['outputDAC'].editingFinished.connect(self._sendParamsDAC)

        self._widgets['valTarget'].editingFinished.connect(self._getStabilizerSettings)

        self._widgets['checkAllan'].stateChanged.connect(self._AllanChanged)

        self._widgets['checkAutosave'].stateChanged.connect(self._enableAutosave)

    # ADC connection
    def _connectADC(self):

        if not self._flagADCConnected:
            if not self._getParamsADC():
                return False
            self._qPOCI.put({'dev': 'ADC', 'cmd': 'connect'})
            self._sendParamsADC()
        else:
            self._qPOCI.put({'dev': 'ADC', 'cmd': 'disconnect'})

        return True

    # ADC settings
    def _getParamsADC(self):

        tmp = {}

        try:
            tmp['Rate'] = self._widgets['comboRate'].currentText()
            tmp['Rate value'] = rate_values[tmp['Rate']]
            tmp['Frequency sampling [Hz]'] = 1/tmp['Rate value']
            tmp['Channels'] = self._widgets['comboChannelsADC'].currentText()
        except ValueError:
            dialogWarning('Could not read parameters!')
            return False

        self._paramsADC = tmp

        # GUI settings
        self._widgets['filters'].setSampling(tmp['Frequency sampling [Hz]'])
        self._widgets['labelSampling'].setText('Sampling: {:.0f} Hz'.format(tmp['Frequency sampling [Hz]']))

        # update ts
        self._ts = np.arange(0, self._N)*self._paramsADC['Rate value']

        # Allan deviation tau recalculation
        self._AllanDevSettings()

        return True

    def _sendParamsADC(self):
        
        if not self._getParamsADC():
            return False
        
        self._qPOCI.put({'dev': 'ADC', 'cmd': 'rate', 'args': self._paramsADC['Rate']})
        print('Rate changed to {}'.format(self._paramsADC['Rate']))

        self._qPOCI.put({'dev': 'ADC', 'cmd': 'channels', 'args': self._paramsADC['Channels']})
        print('Channels changed to {}'.format(self._paramsADC['Channels']))

        self._resetVariables()

    # DAC connection
    def _connectDAC(self):

        if not self._flagDACConnected:
            self._qPOCI.put({
                'dev': 'DAC',
                'cmd': 'connect'
            })
        else:
            self._qPOCI.put({
                'dev': 'DAC',
                'cmd': 'disconnect'
            })
    
    # DAC settings
    def _sendParamsDAC(self):

        # DAC output
        tmp = {
            'dev': 'DAC',
            'cmd': 'freq'
        }

        try:
            tmp['args'] = float(self._widgets['outputDAC'].text())
        except ValueError:
            dialogWarning('Could not read DAC frequency!')
            return False

        self._qPOCI.put(tmp)

        return True

    def _enableDAC(self):

        if not self._flagDACConnected:
            dialogWarning('Connect to DAC first!')
            return False

        if not self._flagDACEnabled:
            self._sendParamsDAC()
            self._qPOCI.put({'dev': 'DAC', 'cmd': 'en', 'args': 1})
            self._flagDACEnabled = True
            self._widgets['btnDACEnable'].setText('Disable')
        else:
            if self._flagLocked:
                dialogWarning('Disengage lock first!')
                return False
            self._qPOCI.put({'dev': 'DAC', 'cmd': 'en', 'args': 0})
            self._flagDACEnabled = False
            self._widgets['btnDACEnable'].setText('Enable')

        return True

    # Stabilizer settings
    def _resetVariables(self):

        # Reset frequencies
        self._val1 = np.zeros(self._N) * np.nan
        self._val2 = np.zeros(self._N) * np.nan
        self._valAvg = np.zeros(self._N) * np.nan
        # Reset stabilization parameters
        self._pv = np.zeros(self._N) * np.nan
        self._error_Hz = np.zeros(self._N) * np.nan
        self._control = np.zeros(self._N) * np.nan
        # Reset Allan deviation
        self._AllanDevs = np.zeros(self._tauN) * np.nan
        # Reset iterators
        self._i = 0
        self._iterAutosave = 0

        return True

    def _setSetpoint(self):

        self._qPOCI.put({
            'dev': 'filt',
            'cmd': 'sp',
            'args': self._valTarget
        })

    def _getStabilizerSettings(self):

        try:
            self._valTarget = float(self._widgets['valTarget'].text())
        except ValueError:
            dialogWarning('Invalid stabilizer settings!')
            return False

        self._setSetpoint()
        
        return True

    def _setFilter(self):

        print('Setting loop filter')
        # Frequency
        filterParams = self._widgets['filters'].filterCoefs()
        if not filterParams:
            self._flagLockReady = False
            return

        filterParams['params']['dt'] = self._paramsADC['Rate value']
        msg = {
            'dev': 'filt',
            'cmd': 'filt',
            'type': filterParams['type'],
            'params': filterParams['params']
        }
        with open('./logs/filter_freq_params.yml', 'w') as f:
            yaml.dump(msg, f)
        self._qPOCI.put(msg)

        self._widgets['labelFilter'].setText(filterParams['type'])
            
        # Lock ready status
        self._flagLockReady = True
        dialogInformation('Filter set successfully!')

    def _lock(self):

        if not self._flagLocked:
            if not self._flagLockReady:
                dialogWarning('Set filter first!')
                return False
            elif not self._flagDACEnabled:
                dialogWarning('Enable DAC first!')
                return False
            else:
                self._setSetpoint()
                self._qPOCI.put({
                    'dev': 'filt',
                    'cmd': 'lock',
                    'args': 1
                })

                self._flagLocked = True
                self._widgets['btnLock'].setText('Unlock')
        else:
            self._qPOCI.put({
                    'dev': 'filt',
                    'cmd': 'lock',
                    'args': 0
                })

            self._flagLocked = False
            self._widgets['btnLock'].setText('Lock')

        return True

    def _resetFilter(self):

        self._qPOCI.put({
            'dev': 'filt',
            'cmd': 'reset'
        })
                            
    # Updating
    def _update(self, eventStop, qPICO):

        print('Starting update thread')
        flagNewData = False
        while True:
            if eventStop.is_set():
                break
            now = time.time()

            # Command parsing
            # print('Queue size: {}'.format(qPICO.qsize()))
            while not qPICO.empty():
                tmp = qPICO.get()
                # ADC
                if tmp['dev'] == 'ADC':
                    # ADC connection
                    if tmp['cmd'] == 'connection':
                        self._flagADCConnected = tmp['args']
                        if self._flagADCConnected:
                            self._widgets['btnADCConnect'].setText('Disconnect')
                        else:
                            self._widgets['btnADCConnect'].setText('Connect')
                    # ADC data
                    elif tmp['cmd'] == 'data':
                        flagNewData = True
                        self._val1[self._i] = tmp['args'][0]
                        self._val2[self._i] = tmp['args'][1]
                        self._valAvg[self._i] = np.average(tmp['args'])
                # DAC
                elif tmp['dev'] == 'DAC':
                    # DAC connection
                    if tmp['cmd'] == 'connection':
                        self._flagDACConnected = tmp['args']
                        if self._flagDACConnected:
                            self._widgets['btnDACConnect'].setText('Disconnect')
                        else:
                            self._widgets['btnDACConnect'].setText('Connect')
                            if self._flagLocked:
                                self._lock() # unlock
                            if self._flagDACEnabled: # software disable DAC
                                self._flagDACEnabled = False
                                self._widgets['btnDACEnable'].setText('Enable')
                # Filter
                elif tmp['dev'] == 'filt':
                    # Process variable
                    if tmp['cmd'] == 'pv':
                        self._pv[self._i] = tmp['args']
                        self._error_Hz[self._i] = self._valTarget - self._valAvg[self._i]
                    # Control
                    elif tmp['cmd'] == 'control':
                        self._control[self._i] = tmp['args']
                else:
                    print('Unknown device! dev: {0} cmd: {1}'.format(tmp['dev'], tmp['cmd']))

            # New data handling
            if flagNewData:
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
                self._pv = np.roll(self._pv, -1)
                self._pv[-1] = np.nan
                self._error_Hz = np.roll(self._error_Hz, -1)
                self._error_Hz[-1] = np.nan
                self._control = np.roll(self._control, -1)
                self._control[-1] = np.nan

            '''
            # Update plots
            if (now - self._timestampUpdatePlots) > cfg.updateTimestepPlots:
                self._timestampUpdatePlots = now
                self._updatePlots()

            # Update Allan
            if (now - self._timestampUpdateAllan) > cfg.updateTimestepAllan:
                self._timestampUpdateAllan = now
                self._updateAllan()
            '''

            time.sleep(cfg.updateTimestep)

        print('Closing update thread')

    # Update plots
    def _updatePlots(self):

        # print('Starting plots update thread')
        # while True:
        #     if eventStop.is_set():
        #         break

        #     self.updatePlots.emit()

        #     # Led lock indicator
        #     if self._flagLocked:
        #         if (np.absolute(self._error_Hz[self._i]) < cfg.errorMargin):
        #             self._widgets['ledLock'].setChecked(True)
        #         else:
        #             self._widgets['ledLock'].setChecked(False)

        #     time.sleep(cfg.updateTimestepPlots)
        # print('Closing plots update thread')


        self.updatePlots.emit()

        # Led lock indicator
        if self._flagLocked:
            if (np.absolute(self._error_Hz[self._i]) < cfg.errorMargin):
                self._widgets['ledLock'].setChecked(True)
            else:
                self._widgets['ledLock'].setChecked(False)

    # Allan deviation
    def _AllanChanged(self):

        if self._widgets['checkAllan'].isChecked():
            self._flagAllan = True
        else:
            self._flagAllan = False
            self._AllanDevs = np.zeros(self._tauN) * np.nan
            self._plotAllan()

    def _AllanDevSettings(self):

        tauMin = 1 / (self._paramsADC['Frequency sampling [Hz]'] - cfg.tauMargin)
        tauMax = self._N / 2 / (self._paramsADC['Frequency sampling [Hz]'] + cfg.tauMargin)

        self._taus = np.linspace(tauMin, tauMax, self._tauN)

        return True

    def _calcAllanDeviation(self):

        if self._i < 1:
            return False

        tauMaxCurrent = (self._i+1) / 2 / (self._paramsADC['Frequency sampling [Hz]'] + cfg.tauMargin)
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
            self._paramsADC['Frequency sampling [Hz]']
        )
        # print(phase_error)
        for i in range(n):
            self._AllanDevs[i] = freq_stab.calc_ADEV_overlapped_single(
                phase_error,
                self._taus[i],
                self._paramsADC['Frequency sampling [Hz]']
            )
        # print(self._taus, self._AllanDevs)

    def _updateAllan(self):

        # print('Starting Allan update thread')
        # while True:
        #     if eventStop.is_set():
        #         break

        #     if self._flagAllan:
        #         try:
        #             self._calcAllanDeviation()
        #         except Exception as e:
        #             print('Could not calculate allan deviation! ', e, flush=True)
        #         self.updatePlotAllan.emit()

        #     time.sleep(cfg.updateTimestepAllan)
        
        # print('Closing Allan update thread')

        if self._flagAllan:
            try:
                self._calcAllanDeviation()
            except Exception as e:
                print('Could not calculate allan deviation! ', e, flush=True)
            self.updatePlotAllan.emit()

    # Plotting
    def _changedLowerPlotShow(self):

        self._lowerPlot = self._widgets['comboShow'].currentText()

        if self._lowerPlot == 'Error [Hz]':
            self._widgets['plotStabilizer'].setLabel("left", "Error [Hz]" )
        elif self._lowerPlot == 'Error [period]':
            self._widgets['plotStabilizer'].setLabel("left", "Error [period]" )
        elif self._lowerPlot == 'Process variable':
            self._widgets['plotStabilizer'].setLabel("left", "Process variable [Hz]")
        elif self._lowerPlot == 'Control':
            self._widgets['plotStabilizer'].setLabel("left", "Control [Hz]" )

    def _plotFreq(self):

        # Frequency plot
        self._curveFreq1.setData(self._ts[:self._i], self._val1[:self._i])
        self._curveFreq2.setData(self._ts[:self._i], self._val2[:self._i])
        self._curvePV.setData(self._ts[:self._i], self._valAvg[:self._i])

        # Error and control plot
        if self._lowerPlot == 'Error [Hz]':
            self._curveError.setData(self._ts[:self._i], self._error_Hz[:self._i])
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
            'ADC channels': self._widgets['comboChannelsADC'].currentText(),
            'ADC channels index': self._widgets['comboChannelsADC'].currentIndex(),
            'DAC output [V]': float(self._widgets['outputDAC'].text())
        }

        params['Setpoint [V]'] = float(self._widgets['valTarget'].text())

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
        if params is None:
            print('Could not import parameters!')
            return False

        try:
            # Set frequency counter params
            self._widgets['comboRate'].setCurrentIndex(params['Rate index'])
            self._widgets['comboChannelsADC'].setCurrentIndex(params['ADC channels index'])
            # Set DAC params
            self._widgets['outputDAC'].setText('{:g}'.format(params['DAC output [V]']))
            # Set stabilization params
            self._widgets['valTarget'].setText('{:g}'.format(params['Setpoint [V]']))
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

        data = {
            'Time [s]': self._ts[:self._i],
            'Frequency 1 [Hz]': self._val1[:self._i],
            'Frequency 2 [Hz]': self._val2[:self._i],
            'Frequency avg [Hz]': self._valAvg[:self._i],
            'Process variable [Hz]': self._pv[:self._i],
            'Error [Hz]': self._error_Hz[:self._i],
            'Control [Hz]': self._control[:self._i]
        }
        if timestamp:
            data['Timestamp [s]'] = self._timestampAutosave[:self._i]

        meta = {
            'Setpoint [V]': self._widgets['valTarget'].text(),
            'Rate [s]': self._paramsADC['Rate value']
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
            if not self._flagADCConnected:
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
