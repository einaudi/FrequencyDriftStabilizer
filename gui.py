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


tau_margin = 0.1 # Hz
error_margin = 5 # Hz
update_timestep = 5e-3 # s

availableFilesCfg = '(*.yml *.yaml)'
availableFilesData = '(*.csv)'


def _handleStab(q, conn, eventDisconnect):

    print('Starting stabilization process', flush=True)
    handler = handlerStabilization(q, conn)

    while True:
        start = time.time()
        # check for disconnect
        if eventDisconnect.is_set():
            handler.disconnect()
            break

        # acquire data
        handler.measure()

        # control
        handler.filterUpdate()

        # check queue
        while not handler.queueEmpty():
            handler.parseCommand()

        stop = time.time()
        to_wait =  handler.wait(start, stop)
        if to_wait < 0:
            print('[{0}] Wait time over sampling period! Delay: {1} s'.format(datetime.now(), to_wait), flush=True)
    conn.close()
    print('Closing stabilization process')


class FrequencyDriftStabilizer(QMainWindow):

    updatePlots = pyqtSignal()
    updatePlotAllan = pyqtSignal()
    updateDevicesFC = pyqtSignal(list)
    autosave = pyqtSignal()

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
        self._freqs1 = np.zeros(self._N) * np.nan # Hz
        self._freqs2 = np.zeros(self._N) * np.nan # Hz
        self._freqsAvg = np.zeros(self._N) * np.nan # Hz
        self._pv = np.zeros(self._N) * np.nan # Hz
        self._error = np.zeros(self._N) * np.nan # Hz
        self._control = np.zeros(self._N) * np.nan # Hz
        self._freqTarget = 0

        self._tauN = 20 # number of points for Allan deviation plot
        self._taus = np.zeros(self._tauN)
        self._AllanDevs = np.zeros(self._tauN) * np.nan

        self._iterAutosave = 0
        self._timestampAutosave = np.zeros(self._N)

        self._lowerPlot = 'Error'

        # Flags
        self._flagFCConnected = False
        self._flagDDSConnected = False
        self._flagDDSEnabled = False
        self._flagFilterDesigned = False
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

        self._getDevicesFC()
        self._getParamsFC()
        if not self._importParams(True):
            self._getStabilizerSettings() 

        print('Running application')
        self.show()

    def closeEvent(self, event):

        self._eventStop.set()
        self._threadUpdate.join()
        if self._flagAutosave:
            self.autosave.emit()

        self._eventDisconnect.set()
        self._processStab.join()
        self._stabConn.close()

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
        self._curveAllan = self._widgets['plotAllan'].plot(pen='y')
        # self._widgets['checkAllan'].setChecked(True)

        # Setting combos in settings section
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

        self._widgets['btnFCConnect'].clicked.connect(self._connectFC)
        self._widgets['btnRefresh'].clicked.connect(self._getDevicesFC)
        self._widgets['btnDDSConnect'].clicked.connect(self._connectDDS)
        self._widgets['btnDDSEnable'].clicked.connect(self._enableDDS)
        self._widgets['btnLock'].clicked.connect(self._lock)
        self._widgets['btnResetFilter'].clicked.connect(self._resetFilter)
        self._widgets['btnResetPlot'].clicked.connect(self._resetVariables)

        self.updatePlots.connect(self._plotFreq)
        self.updatePlotAllan.connect(self._plotAllan)
        self.updateDevicesFC.connect(self._updateDevicesListFC)
        self.autosave.connect(self._autosave)

        self._widgets['comboRate'].currentIndexChanged.connect(self._sendParamsFC)
        self._widgets['comboShow'].currentIndexChanged.connect(self._changedLowerPlotShow)

        self._widgets['freqDDS'].editingFinished.connect(self._sendParamsDDS)
        self._widgets['ampDDS'].editingFinished.connect(self._sendParamsDDS)

        self._widgets['freqTarget'].editingFinished.connect(self._getStabilizerSettings)
        self._widgets['checkLowpass'].stateChanged.connect(self._applyLowpass)
        self._widgets['filters'].newFilterDesigned.connect(self._setFilter)

        self._widgets['checkAllan'].stateChanged.connect(self._AllanChanged)

        self._widgets['checkAutosave'].stateChanged.connect(self._enableAutosave)

    # FC connection
    def _getDevicesFC(self):

        self._queueStab.put({'dev': 'FC', 'cmd': 'devices'})

    def _updateDevicesListFC(self, devs):

        self._widgets['comboUSB'].clear()
        self._widgets['comboUSB'].addItems(devs)

    def _connectFC(self):

        if not self._flagFCConnected:
            if not self._getParamsFC():
                return False
            address = self._widgets['comboUSB'].currentText()
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
        except ValueError:
            dialogWarning('Could not read parameters!')
            return False

        self._paramsFC = tmp

        self._widgets['filters'].setSampling(tmp['Frequency sampling [Hz]'])
        self._widgets['labelSampling'].setText('{:.0f} Hz'.format(tmp['Frequency sampling [Hz]']))

        # update ts
        self._ts = np.arange(0, self._N)*self._paramsFC['Rate value']

        # Allan deviation settings
        self._AllanDevSettings()

        return True

    def _sendParamsFC(self):
        
        if not self._getParamsFC():
            return False
        
        self._queueStab.put({'dev': 'FC', 'cmd': 'rate', 'args': self._paramsFC['Rate']})
        print('Rate changed to {}'.format(self._paramsFC['Rate']))

        self._resetVariables()

    # DDS settings
    def _connectDDS(self):

        if not self._flagDDSConnected:
            conn = self._widgets['connDDS'].text()
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
    def _resetVariables(self):

        # Reset frequencies
        self._freqs1 = np.zeros(self._N) * np.nan
        self._freqs2 = np.zeros(self._N) * np.nan
        self._freqsAvg = np.zeros(self._N) * np.nan
        # Reset stabilization parameters
        self._pv = np.zeros(self._N) * np.nan
        self._error = np.zeros(self._N) * np.nan
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
            'args': self._freqTarget
        })

    def _getStabilizerSettings(self):

        try:
            self._freqTarget = float(self._widgets['freqTarget'].text())
        except ValueError:
            dialogWarning('Invalid stabilizer settings!')
            return False

        self._setSetpoint()
        
        return True

    def _setFilter(self, filterParams):

        if filterParams['filterType'] == 'pid':
            self._flagFilterDesigned = True
            filterParams['params']['dt'] = self._paramsFC['Rate value']

        self._queueStab.put({
            'dev': 'filt',
            'cmd': 'filt',
            'type': filterParams['filterType'],
            'params': filterParams['params']
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
            if not self._flagFilterDesigned:
                dialogWarning('Design filter first!')
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

        if self._flagFilterDesigned:
            self._queueStab.put({
                'dev': 'filt',
                'cmd': 'reset'
            })

    # Updating
    def _update(self, eventStop, conn):

        print('Starting update thread')
        flagNewData = False
        while True:
            if eventStop.is_set():
                break

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
                        self._freqs1[self._i] = tmp['args'][0]
                        self._freqs2[self._i] = tmp['args'][1]
                        self._freqsAvg[self._i] = np.average(tmp['args'])
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
                # Filter
                elif tmp['dev'] == 'filt':
                    # Filter process variable signal
                    if tmp['cmd'] == 'pv':
                        self._pv[self._i] = tmp['args']
                        self._error[self._i] = self._pv[self._i] - self._freqTarget
                    # Filter control signal
                    elif tmp['cmd'] == 'control':
                        self._control[self._i] = tmp['args']
                else:
                    print('Unknown device! dev: {0} cmd: {1}'.format(tmp['dev'], tmp['cmd']))

            if flagNewData:
                if self._flagAllan:
                    try:
                        self._calcAllanDeviation()
                    except Exception as e:
                        print('Could not calculate allan deviation! ', e, flush=True)
                    self.updatePlotAllan.emit()

                self.updatePlots.emit()

                # Led lock indicator
                if (np.absolute(self._error[self._i]) < error_margin) and self._flagLocked:
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
                    self.autosave.emit()

            if self._i >= self._N:
                self._i = self._N-1
                self._freqs1 = np.roll(self._freqs1, -1)
                self._freqs2 = np.roll(self._freqs2, -1)
                self._freqsAvg = np.roll(self._freqsAvg, -1)
                self._pv = np.roll(self._pv, -1)
                self._error = np.roll(self._error, -1)
                self._control = np.roll(self._control, -1)

            time.sleep(update_timestep)
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

        tauMin = 1 / (self._paramsFC['Frequency sampling [Hz]'] - tau_margin)
        tauMax = self._N / 2 / (self._paramsFC['Frequency sampling [Hz]'] + tau_margin)

        self._taus = np.linspace(tauMin, tauMax, self._tauN)

        return True

    def _calcAllanDeviation(self):

        if self._i < 1:
            return False

        tauMaxCurrent = (self._i+1) / 2 / (self._paramsFC['Frequency sampling [Hz]'] + tau_margin)
        n = 0
        for tau in self._taus:
            if tau <= tauMaxCurrent:
                n += 1
            else:
                break

        fs = self._freqsAvg[~np.isnan(self._freqsAvg)]
        fs_frac = freq_stab.calc_fractional_frequency(
            fs,
            self._freqTarget
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

    # Plotting
    def _changedLowerPlotShow(self):

        self._lowerPlot = self._widgets['comboShow'].currentText()

        if self._lowerPlot == 'Error':
            self._widgets['plotStabilizer'].setLabel("left", "Error [Hz]" )
        elif self._lowerPlot == 'Control':
            self._widgets['plotStabilizer'].setLabel("left", "Control [Hz]" )

    def _plotFreq(self):

        # Frequency plot
        self._curveFreq1.setData(self._ts[:self._i], self._freqs1[:self._i])
        self._curveFreq2.setData(self._ts[:self._i], self._freqs2[:self._i])
        self._curvePV.setData(self._ts[:self._i], self._pv[:self._i])

        # Error and control plot
        if self._lowerPlot == 'Error':
            self._curveError.setData(self._ts[:self._i], self._error[:self._i])
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
            'DDS frequency [Hz]': float(self._widgets['freqDDS'].text()),
            'DDS amplitude [%]': float(self._widgets['ampDDS'].text()),
            'Target frequency [Hz]': float(self._widgets['freqTarget'].text()),
            'Lowpass active': self._widgets['checkLowpass'].isChecked()
        }

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

        # Set frequency counter params
        self._widgets['comboRate'].setCurrentIndex(params['Rate index'])
        # Set DDS params
        self._widgets['freqDDS'].setText('{:.9e}'.format(params['DDS frequency [Hz]']))
        self._widgets['ampDDS'].setText('{}'.format(params['DDS amplitude [%]']))
        # Set stabilization params
        self._widgets['freqTarget'].setText('{:.9e}'.format(params['Target frequency [Hz]']))
        self._widgets['checkLowpass'].setChecked(params['Lowpass active'])
        # Set filter params
        self._widgets['filters'].setParams(params['Filters'])

        self._getStabilizerSettings()

        print('Parameters imported from {}'.format(inputPath))
        if not whileInit:
            dialogInformation('Parameters imported succesfully!')
        return True

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

        data = {
            'Time [s]': self._ts[:self._i],
            'Frequency 1 [Hz]': self._freqs1[:self._i],
            'Frequency 2 [Hz]': self._freqs2[:self._i],
            'Frequency avg [Hz]': self._freqsAvg[:self._i],
            'Process variable [Hz]': self._pv[:self._i],
            'Error [Hz]': self._error[:self._i],
            'Control [Hz]': self._control[:self._i]
        }

        meta = {
            'Target frequency [Hz]': self._widgets['freqTarget'].text(),
            'Rate [s]': self._paramsFC['Rate value']
        }

        save_csv(
            data,
            outputPath,
            meta,
            index=False
        )

        print('Frequency data saved to {}'.format(outputPath))
        dialogInformation('Frequency data saved to {}'.format(outputPath))
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

        data = {
            'Timestamp': self._timestampAutosave[:self._iterAutosave],
            'Frequency 1 [Hz]': self._freqs1[:self._iterAutosave],
            'Frequency 2 [Hz]': self._freqs2[:self._iterAutosave],
            'Frequency avg [Hz]': self._freqsAvg[:self._iterAutosave],
            'Process variable [Hz]': self._pv[:self._iterAutosave],
            'Error [Hz]': self._error[:self._iterAutosave],
            'Control [Hz]': self._control[:self._iterAutosave]
        }

        meta = {
            'Target frequency [Hz]': self._widgets['freqTarget'].text(),
            'Rate [s]': self._paramsFC['Rate value']
        }

        path = './data/autosave_{}.csv'.format(time.time())
        save_csv(
            data,
            path,
            meta,
            index=False
        )

        print('[{0}] Autosave'.format(datetime.now()))
        self._iterAutosave = 0


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = FrequencyDriftStabilizer()
    sys.exit(app.exec_())
