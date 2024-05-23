# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTabWidget,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout
)
from PyQt5.QtCore import pyqtSignal
from widgets.Dialogs import dialogWarning, dialogInformation

import src.filterDesign as fd
import config.config as cfg

import numpy as np


class tabLowpass(QWidget):

    newDesign = pyqtSignal()

    def __init__(self):

        super().__init__()

        # Variables
        self._freqSampling = 1
        self._ff_coefs = np.ones(1)
        self._fb_coefs = np.zeros(1)

        # Flags
        self._flagFilterDesigned = False

        # Widgets
        self._freqPassband = QLineEdit('1')
        self._freqStopband = QLineEdit('20')
        self._attPassband = QLineEdit('-1')
        self._attStopband = QLineEdit('-10')
        self._gain = QLineEdit('0')
        self._btnDesign = QPushButton('Design')
        self._labelCutoff = QLabel('0 Hz')
        self._labelOrder = QLabel('Filter order: 0')

        # Layout
        layout = QGridLayout()
        # Passband
        layout.addWidget(QLabel('Passband frequency [Hz]'), 0, 0)
        layout.addWidget(self._freqPassband, 0, 1)
        layout.addWidget(QLabel('Passband attenuation [dB]'), 0, 2)
        layout.addWidget(self._attPassband, 0, 3)
        # Stopband
        layout.addWidget(QLabel('Stopband frequency [Hz]'), 1, 0)
        layout.addWidget(self._freqStopband, 1, 1)
        layout.addWidget(QLabel('Stopband attenuation [dB]'), 1, 2)
        layout.addWidget(self._attStopband, 1, 3)
        # Gain
        layout.addWidget(QLabel('Filter gain [dB]'), 2, 0)
        layout.addWidget(self._gain, 2, 1)
        # Design btn
        layout.addWidget(self._btnDesign, 2, 2, 1, 2)
        # Cutoff frequency
        layout.addWidget(QLabel('Cutoff frequency:'), 3, 0)
        layout.addWidget(self._labelCutoff, 3, 1)
        layout.addWidget(self._labelOrder, 3, 2)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # UI
        self._btnDesign.clicked.connect(self._calcCoefs)

        # Enter pressing
        self._freqPassband.returnPressed.connect(self._calcCoefs)
        self._freqStopband.returnPressed.connect(self._calcCoefs)
        self._attPassband.returnPressed.connect(self._calcCoefs)
        self._attStopband.returnPressed.connect(self._calcCoefs)
        self._gain.returnPressed.connect(self._calcCoefs)

    def _calcCoefs(self):
        '''
        Calculate lowpass IIR filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        try:
            OmegaPassband = 2*np.pi*float(self._freqPassband.text())
            OmegaStopband = 2*np.pi*float(self._freqStopband.text())
            gain_dB = float(self._gain.text())
            attPassband_dB = float(self._attPassband.text())
            attPassband = fd.dB_to_att(attPassband_dB - gain_dB)
            attStopband_dB = float(self._attStopband.text())
            attStopband = fd.dB_to_att(attStopband_dB - gain_dB)
        except ValueError:
            dialogWarning('Could not read parameters!')
            return False

        # Check Nyquist frequency
        if(
            OmegaPassband >= np.pi*self._freqSampling
            or OmegaStopband >= np.pi*self._freqSampling
        ):
            dialogWarning('Critical frequencies above Nyquist frequency!')
            return False
        # Check critical frequencies
        if OmegaPassband >= OmegaStopband:
            dialogWarning('Passband frequency above stopband frequency!')
            return False
        # Check attenuations
        if attPassband_dB > gain_dB:
            dialogWarning('Passband attenuation above gain')
            return False
        if attStopband_dB > gain_dB:
            dialogWarning('Stopband attenuation above gain')
            return False
        if attPassband <= attStopband:
            dialogWarning('Passband attenuation below stopband attenuation!')
            return False

        # Order
        N = fd.calc_order(OmegaPassband, OmegaStopband, attPassband, attStopband)
        self._labelOrder.setText('Filter order: {}'.format(N))
        # Cutoff frequency
        OmegaCutoff = fd.calc_cutoff_freq(OmegaPassband, attPassband, N)
        self._labelCutoff.setText('{:.2e} Hz'.format(OmegaCutoff/2/np.pi))

        fb_coefs, ff_coefs, _ = fd.get_digital_filter_coefs(
            N,
            OmegaCutoff,
            2*np.pi*self._freqSampling
        )
        ff_coefs *= fd.dB_to_att(gain_dB)

        self._ff_coefs = ff_coefs
        self._fb_coefs = fb_coefs

        self._flagFilterDesigned = True
        print('Lowpass filter designed!', flush=True)

        msg = 'Lowpass filter designed successfully!\n'
        msg += 'Order: {}\n'.format(N)
        msg += 'Cutoff frequency {:.2e} Hz\n'.format(OmegaCutoff/2/np.pi)
        dialogInformation(msg)

        self.newDesign.emit()

        return True

    def setSampling(self, fSampling):
        '''
        Set sampling frequency
        
        Args:
            fSampling: sampling frequency
        '''
        self._freqSampling = fSampling

    def isDesigned(self):
        '''
        Check if filter is already designed

        Returns:
            bool - if filter is designed
        '''
        if self._flagFilterDesigned:
            return True
        else:
            return False

    def filterCoefs(self):
        '''
        Get IIR filter coefficients
        
        Returns:
            tuple: (feed forward coefs, feedback coefs)
        '''
        ret = {
            'type': 'lowpass',
            'params': {
                'ff_coefs': self._ff_coefs,
                'fb_coefs': self._fb_coefs
            }
        }
        return ret

    def getParams(self):
        '''
        Get filter parameters for calculation of IIR coeficients
        
        Returns:
            dict: parameters for filter design
        '''
        ret = {
            'Passband frequency [Hz]': float(self._freqPassband.text()),
            'Stopband frequency [Hz]': float(self._freqStopband.text()),
            'Passband attenuation [dB]': float(self._attPassband.text()),
            'Stopband attenuation [dB]': float(self._attStopband.text()),
            'Gain [dB]': float(self._gain.text()),
            'Sampling frequency [Hz]': float(self._freqSampling)
        }
        if self.isDesigned():
            ret['Feedforward coefs'] = self._ff_coefs.tolist()
            ret['Feedback coefs'] = self._fb_coefs.tolist()

        return ret

    def setParams(self, params):
        '''
        Set filter parameters for calculation of IIR coeficients
        
        Args:
            params: dict with filter parameters
        '''
        try:
            self._freqPassband.setText('{:g}'.format(params['Passband frequency [Hz]']))
            self._freqStopband.setText('{:g}'.format(params['Stopband frequency [Hz]']))
            self._attPassband.setText('{:g}'.format(params['Passband attenuation [dB]']))
            self._attStopband.setText('{:g}'.format(params['Stopband attenuation [dB]']))
            self._gain.setText('{:g}'.format(params['Gain [dB]']))
            self._freqSampling = params['Sampling frequency [Hz]']
        except KeyError:
            dialogWarning('Could not read lowpass filter parameters!')


class tabPID(QWidget):

    newDesign = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        # Variables
        self._coefs = {}

        # Flags
        self._flagFilterDesigned = False

        # Widgets
        self._kp = QLineEdit('3')
        self._ki = QLineEdit('200')
        self._kd = QLineEdit('0.1')
        self._gain = QLineEdit('1')
        self._boundsBtm = QLineEdit('1e6')
        self._boundsTop = QLineEdit('100e6')
        self._intBoundsBtm = QLineEdit('-inf')
        self._intBoundsTop = QLineEdit('inf')
        self._leadCoef = QLineEdit('0.9')
        self._btnDesign = QPushButton('Design')
        self._sign = QComboBox()
        self._sign.addItem('Positive')
        self._sign.addItem('Negative')

        # Layout
        layout = QGridLayout()
        # PID settings
        layout.addWidget(QLabel('kp'), 0, 0)
        layout.addWidget(self._kp, 0, 1)
        layout.addWidget(QLabel('ki'), 1, 0)
        layout.addWidget(self._ki, 1, 1)
        layout.addWidget(QLabel('kd'), 2, 0)
        layout.addWidget(self._kd, 2, 1)
        layout.addWidget(QLabel('Gain'), 3, 0)
        layout.addWidget(self._gain, 3, 1)
        # Bounds
        layout.addWidget(QLabel('Bounds'), 0, 2)
        layout.addWidget(self._boundsBtm, 0, 3)
        layout.addWidget(self._boundsTop, 0, 4)
        layout.addWidget(QLabel('Int bounds'), 1, 2)
        layout.addWidget(self._intBoundsBtm, 1, 3)
        layout.addWidget(self._intBoundsTop, 1, 4)
        # Lead coef
        layout.addWidget(QLabel('Lead coef'), 2, 2)
        layout.addWidget(self._leadCoef, 2, 3, 1, 2)
        # Sign
        layout.addWidget(QLabel('Filter sign'), 3, 2)
        layout.addWidget(self._sign, 3, 3)
        # Button
        layout.addWidget(self._btnDesign, 3, 4)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # UI
        self._btnDesign.clicked.connect(self._calcCoefs)

        # Enter pressed
        self._kp.returnPressed.connect(self._calcCoefs)
        self._ki.returnPressed.connect(self._calcCoefs)
        self._kd.returnPressed.connect(self._calcCoefs)
        self._gain.returnPressed.connect(self._calcCoefs)
        self._boundsBtm.returnPressed.connect(self._calcCoefs)
        self._boundsTop.returnPressed.connect(self._calcCoefs)
        self._intBoundsBtm.returnPressed.connect(self._calcCoefs)
        self._intBoundsTop.returnPressed.connect(self._calcCoefs)
        self._leadCoef.returnPressed.connect(self._calcCoefs)
        self._sign.activated.connect(self._calcCoefs)

    def _calcCoefs(self):
        '''
        Calculate PID filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        tmp = {}
        try:
            tmp['kp'] = float(self._kp.text())
            tmp['ki'] = float(self._ki.text())
            tmp['kd'] = float(self._kd.text())
            tmp['gain'] = float(self._gain.text())
            tmp['bounds'] = [
                float(self._boundsBtm.text()),
                float(self._boundsTop.text())
            ]
            tmp['int_bounds'] = [
                float(self._intBoundsBtm.text()),
                float(self._intBoundsTop.text())
            ]
            tmp['lead_coef'] = float(self._leadCoef.text())
        except ValueError:
            dialogWarning('Could not read parameters!')
            return False

        self._flagFilterDesigned = True
        print('PID filter designed!', flush=True)
        dialogInformation('PID filter designed successfully!')

        self._coefs = tmp
        self.newDesign.emit('PID')

        return True

    def isDesigned(self):
        '''
        Check if filter is already designed

        Returns:
            bool - if filter is designed
        '''
        if self._flagFilterDesigned:
            return True
        else:
            return False

    def filterCoefs(self):
        '''
        Get PID filter coefficients
        
        Returns:
            dict: PID filter coefficients
        '''
        ret = {
            'type': 'PID',
            'params': self._coefs
        }

        # Error calculation sign
        if self._sign.currentText() == 'Positive':
            tmp['params']['sign'] = 1
        elif self._sign.currentText() == 'Negative':
            tmp['params']['sign'] = -1

        return ret

    def getParams(self):
        '''
        Get filter parameters for calculation of PID coeficients
        
        Returns:
            dict: parameters for filter design
        '''
        if self._sign.currentText() == 'Positive':
            sign = 1
        elif self._sign.currentText() == 'Negative':
            sign = -1
        ret = {
            'Type': 'PID',
            'kp': float(self._kp.text()),
            'ki': float(self._ki.text()),
            'kd': float(self._kd.text()),
            'Gain': float(self._gain.text()),
            'Bounds': [float(self._boundsBtm.text()), float(self._boundsTop.text())],
            'Bounds integral': [float(self._intBoundsBtm.text()), float(self._intBoundsTop.text())],
            'Lead coef': float(self._leadCoef.text()),
            'Sign': sign
        }

        return ret

    def setParams(self, params):
        '''
        Set filter parameters for calculation of PID coeficients
        
        Args:
            params: dict with filter parameters
        '''
        try:
            self._kp.setText('{:g}'.format(params['kp']))
            self._ki.setText('{:g}'.format(params['ki']))
            self._kd.setText('{:g}'.format(params['kd']))
            self._gain.setText('{:.4}'.format(params['Gain']))
            self._boundsBtm.setText('{:g}'.format(params['Bounds'][0]))
            self._boundsTop.setText('{:g}'.format(params['Bounds'][1]))
            self._intBoundsBtm.setText('{:g}'.format(params['Bounds integral'][0]))
            self._intBoundsTop.setText('{:g}'.format(params['Bounds integral'][1]))
            self._leadCoef.setText('{:.4}'.format(params['Lead coef']))
            if params['Sign'] == 1:
                self._sign.setCurrentIndex(0)
            elif params['Sign'] == -1:
                self._sign.setCurrentIndex(1)
        except KeyError:
            dialogWarning('Could not read PID filter parameters!', flush=True)

class tabIntLowpass(QWidget):

    newDesign = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        # Variables
        self._coefs = {}
        self._freqSampling = 1
        self._ff_coefs = np.ones(1)
        self._fb_coefs = np.zeros(1)

        # Flags
        self._flagFilterDesigned = False

        # Widgets
        # Integrator
        self._ki = QLineEdit('200')
        self._boundsBtm = QLineEdit('1e6')
        self._boundsTop = QLineEdit('100e6')
        self._intBoundsBtm = QLineEdit('-inf')
        self._intBoundsTop = QLineEdit('inf')
        # Lowpass
        self._freqCutoff = QLineEdit('1')
        self._filterOrder = QLineEdit('1')
        self._gain = QLineEdit('0')
        self._sign = QComboBox()
        self._sign.addItem('Positive')
        self._sign.addItem('Negative')
        # Total gain
        self._gainTotal = QLineEdit('0')
        
        self._btnDesign = QPushButton('Design')

        # Layout
        layout = QGridLayout()
        # Integrator settings
        layout.addWidget(QLabel('Integrator'), 0, 0)
        layout.addWidget(self._ki, 0, 1)
        layout.addWidget(QLabel('Integrators bounds'), 0, 2)
        layout.addWidget(self._intBoundsBtm, 0, 3)
        layout.addWidget(self._intBoundsTop, 0, 4)
        # Bounds
        layout.addWidget(QLabel('Bounds'), 1, 2)
        layout.addWidget(self._boundsBtm, 1, 3)
        layout.addWidget(self._boundsTop, 1, 4)
        # Cutoff
        layout.addWidget(QLabel('Cutoff frequency [Hz]'), 2, 0)
        layout.addWidget(self._freqCutoff, 2, 1)
        # Order
        layout.addWidget(QLabel('Filter order'), 2, 2)
        layout.addWidget(self._filterOrder, 2, 3, 1, 2)
        # Gain
        layout.addWidget(QLabel('Lowpass gain [dB]'), 3, 0)
        layout.addWidget(self._gain, 3, 1)
        # Total gain
        layout.addWidget(QLabel('Total gain [dB]'), 4, 0)
        layout.addWidget(self._gainTotal, 4, 1)
        # Sign
        layout.addWidget(QLabel('Filter sign'), 4, 2)
        layout.addWidget(self._sign, 4, 3)
        # Design btn
        layout.addWidget(self._btnDesign, 4, 4)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # UI
        self._btnDesign.clicked.connect(self._calcCoefs)

        # Return pressed
        self._ki.returnPressed.connect(self._calcCoefs)
        self._boundsBtm.returnPressed.connect(self._calcCoefs)
        self._boundsTop.returnPressed.connect(self._calcCoefs)
        self._intBoundsBtm.returnPressed.connect(self._calcCoefs)
        self._intBoundsTop.returnPressed.connect(self._calcCoefs)
        self._freqCutoff.returnPressed.connect(self._calcCoefs)
        self._filterOrder.returnPressed.connect(self._calcCoefs)
        self._gain.returnPressed.connect(self._calcCoefs)
        self._sign.activated.connect(self._calcCoefs)

    def isDesigned(self):
        '''
        Check if filter is already designed

        Returns:
            bool - if filter is designed
        '''
        if self._flagFilterDesigned:
            return True
        else:
            return False
    
    def setSampling(self, fSampling):
        '''
        Set sampling frequency
        
        Args:
            fSampling: sampling frequency
        '''
        self._freqSampling = fSampling

    def _calcCoefsIntegrator(self):
        '''
        Calculate PID filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        tmp = {}
        try:
            tmp['ki'] = float(self._ki.text())
            tmp['bounds'] = [
                float(self._boundsBtm.text()),
                float(self._boundsTop.text())
            ]
            tmp['int_bounds'] = [
                float(self._intBoundsBtm.text()),
                float(self._intBoundsTop.text())
            ]
        except ValueError:
            dialogWarning('Could not read integrator parameters!')
            return False

        self._coefs = tmp

        return True
    
    def _calcCoefsLowpass(self):
        '''
        Calculate lowpass IIR filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        try:
            OmegaCutoff = 2*np.pi*float(self._freqCutoff.text())
            gain_dB = float(self._gain.text())
            filterOrder = int(float(self._filterOrder.text()))
        except ValueError:
            dialogWarning('Could not read lowpass parameters!')
            return False

        # Check Nyquist frequency
        if OmegaCutoff >= np.pi*self._freqSampling:
            dialogWarning('Critical frequency above Nyquist frequency!')
            return False
        # Check attenuations
        if filterOrder <= 0:
            dialogWarning('Filter order must be positive')
            return False

        fb_coefs, ff_coefs, _ = fd.get_digital_filter_coefs(
            filterOrder,
            OmegaCutoff,
            2*np.pi*self._freqSampling
        )
        ff_coefs *= fd.dB_to_att(gain_dB)

        self._ff_coefs = ff_coefs
        self._fb_coefs = fb_coefs

        return True
    
    def _calcCoefs(self):

        if self._calcCoefsIntegrator():
            if self._calcCoefsLowpass():
                self._flagFilterDesigned = True
                print('Loop filter designed!', flush=True)
                self.newDesign.emit('IntLowpass')

    def filterCoefs(self):

        tmp = {
            'type': 'IntLowpass',
            'params': self._coefs
        }
        tmp['params']['ff_coefs'] = self._ff_coefs.tolist()
        tmp['params']['fb_coefs'] = self._fb_coefs.tolist()

        # Error calculation sign
        if self._sign.currentText() == 'Positive':
            tmp['params']['sign'] = 1
        elif self._sign.currentText() == 'Negative':
            tmp['params']['sign'] = -1

        # Total gain
        try:
            tmp['params']['gain'] = float(self._gainTotal.text())
        except ValueError:
            dialogWarning('Could not read total gain! Setting to 0')
            tmp['params']['gain'] = 0
        
        return tmp
    
    def getParams(self):
        '''
        Get filter parameters for calculation of PID coeficients
        
        Returns:
            dict: parameters for filter design
        '''
        if self._sign.currentText() == 'Positive':
            sign = 1
        elif self._sign.currentText() == 'Negative':
            sign = -1
        ret = {
            'Type': 'IntLowpass',
            'ki': float(self._ki.text()),
            'Bounds': [float(self._boundsBtm.text()), float(self._boundsTop.text())],
            'Bounds integral': [float(self._intBoundsBtm.text()), float(self._intBoundsTop.text())],
            'Cutoff frequency [Hz]': float(self._freqCutoff.text()),
            'Filter order': float(self._filterOrder.text()),
            'Sampling frequency [Hz]': float(self._freqSampling),
            'Sign': sign,
            'Gain [dB]': float(self._gain.text())
        }
        if self.isDesigned():
            ret['Feedforward coefs'] = self._ff_coefs.tolist()
            ret['Feedback coefs'] = self._fb_coefs.tolist()

        return ret

    def setParams(self, params):
        '''
        Set filter parameters for calculation of PID coeficients
        
        Args:
            params: dict with filter parameters
        '''
        try:
            self._ki.setText('{:g}'.format(params['ki']))
            self._boundsBtm.setText('{:g}'.format(params['Bounds'][0]))
            self._boundsTop.setText('{:g}'.format(params['Bounds'][1]))
            self._intBoundsBtm.setText('{:g}'.format(params['Bounds integral'][0]))
            self._intBoundsTop.setText('{:g}'.format(params['Bounds integral'][1]))
            self._freqCutoff.setText('{:g}'.format(params['Cutoff frequency [Hz]']))
            self._filterOrder.setText('{:g}'.format(params['Filter order']))
            self._gain.setText('{:g}'.format(params['Gain [dB]']))
            self._freqSampling = params['Sampling frequency [Hz]']
            if params['Sign'] == 1:
                self._sign.setCurrentIndex(0)
            elif params['Sign'] == -1:
                self._sign.setCurrentIndex(1)
        except KeyError:
            dialogWarning('Could not read loop filter parameters!')

class tabDoubleIntLowpass(QWidget):

    newDesign = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        # Variables
        self._coefs = {}
        self._freqSampling = 1
        self._ff_coefs = np.ones(1)
        self._fb_coefs = np.zeros(1)

        # Flags
        self._flagFilterDesigned = False

        # Widgets
        # Integrator
        self._ki = QLineEdit('200')
        self._intBoundsBtm = QLineEdit('-inf')
        self._intBoundsTop = QLineEdit('inf')
        # Double integrator
        self._kii = QLineEdit('0')
        # Lowpass
        self._freqCutoff = QLineEdit('1')
        self._filterOrder = QLineEdit('1')
        self._gain = QLineEdit('0')
        # General
        self._boundsBtm = QLineEdit('1e6')
        self._boundsTop = QLineEdit('100e6')
        self._sign = QComboBox()
        self._sign.addItem('Positive')
        self._sign.addItem('Negative')
        # Total gain
        self._gainTotal = QLineEdit('0')
        
        self._btnDesign = QPushButton('Design')

        # Layout
        layout = QGridLayout()
        # Integrator settings
        layout.addWidget(QLabel('Integrator'), 0, 0)
        layout.addWidget(self._ki, 0, 1)
        layout.addWidget(QLabel('Integrators bounds'), 0, 2)
        layout.addWidget(self._intBoundsBtm, 0, 3)
        layout.addWidget(self._intBoundsTop, 0, 4)
        # Double integrator settings
        layout.addWidget(QLabel('Double integrator'), 1, 0)
        layout.addWidget(self._kii, 1, 1)
        # Bounds
        layout.addWidget(QLabel('Bounds'), 1, 2)
        layout.addWidget(self._boundsBtm, 1, 3)
        layout.addWidget(self._boundsTop, 1, 4)
        # Cutoff
        layout.addWidget(QLabel('Cutoff frequency [Hz]'), 2, 0)
        layout.addWidget(self._freqCutoff, 2, 1)
        # Order
        layout.addWidget(QLabel('Filter order'), 2, 2)
        layout.addWidget(self._filterOrder, 2, 3, 1, 2)
        # Gain
        layout.addWidget(QLabel('Lowpass gain [dB]'), 3, 0)
        layout.addWidget(self._gain, 3, 1)
        # Total gain
        layout.addWidget(QLabel('Total gain [dB]'), 4, 0)
        layout.addWidget(self._gainTotal, 4, 1)
        # Sign
        layout.addWidget(QLabel('Filter sign'), 4, 2)
        layout.addWidget(self._sign, 4, 3)
        # Design btn
        layout.addWidget(self._btnDesign, 4, 4)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # UI
        self._btnDesign.clicked.connect(self._calcCoefs)

        # Return pressed
        self._ki.returnPressed.connect(self._calcCoefs)
        self._kii.returnPressed.connect(self._calcCoefs)
        self._boundsBtm.returnPressed.connect(self._calcCoefs)
        self._boundsTop.returnPressed.connect(self._calcCoefs)
        self._intBoundsBtm.returnPressed.connect(self._calcCoefs)
        self._intBoundsTop.returnPressed.connect(self._calcCoefs)
        self._freqCutoff.returnPressed.connect(self._calcCoefs)
        self._filterOrder.returnPressed.connect(self._calcCoefs)
        self._gain.returnPressed.connect(self._calcCoefs)
        self._sign.activated.connect(self._calcCoefs)

    def isDesigned(self):
        '''
        Check if filter is already designed

        Returns:
            bool - if filter is designed
        '''
        if self._flagFilterDesigned:
            return True
        else:
            return False
    
    def setSampling(self, fSampling):
        '''
        Set sampling frequency
        
        Args:
            fSampling: sampling frequency
        '''
        self._freqSampling = fSampling

    def _calcCoefsIntegrator(self):
        '''
        Calculate PID filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        tmp = {}
        try:
            tmp['ki'] = float(self._ki.text())
            tmp['kii'] = float(self._kii.text())
            tmp['bounds'] = [
                float(self._boundsBtm.text()),
                float(self._boundsTop.text())
            ]
            tmp['int_bounds'] = [
                float(self._intBoundsBtm.text()),
                float(self._intBoundsTop.text())
            ]
        except ValueError:
            dialogWarning('Could not read integrator parameters!')
            return False

        self._coefs = tmp

        return True
    
    def _calcCoefsLowpass(self):
        '''
        Calculate lowpass IIR filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        try:
            OmegaCutoff = 2*np.pi*float(self._freqCutoff.text())
            gain_dB = float(self._gain.text())
            filterOrder = int(float(self._filterOrder.text()))
        except ValueError:
            dialogWarning('Could not read lowpass parameters!')
            return False

        # Check Nyquist frequency
        if OmegaCutoff >= np.pi*self._freqSampling:
            dialogWarning('Critical frequency above Nyquist frequency!')
            return False
        # Check attenuations
        if filterOrder <= 0:
            dialogWarning('Filter order must be positive')
            return False

        fb_coefs, ff_coefs, _ = fd.get_digital_filter_coefs(
            filterOrder,
            OmegaCutoff,
            2*np.pi*self._freqSampling
        )
        ff_coefs *= fd.dB_to_att(gain_dB)

        self._ff_coefs = ff_coefs
        self._fb_coefs = fb_coefs

        return True
    
    def _calcCoefs(self):

        if self._calcCoefsIntegrator():
            if self._calcCoefsLowpass():
                self._flagFilterDesigned = True
                print('Loop filter designed!', flush=True)
                self.newDesign.emit('DoubleIntLowpass')

    def filterCoefs(self):

        tmp = {
            'type': 'DoubleIntLowpass',
            'params': self._coefs
        }
        tmp['params']['ff_coefs'] = self._ff_coefs.tolist()
        tmp['params']['fb_coefs'] = self._fb_coefs.tolist()

        # Error calculation sign
        if self._sign.currentText() == 'Positive':
            tmp['params']['sign'] = 1
        elif self._sign.currentText() == 'Negative':
            tmp['params']['sign'] = -1

        # Total gain
        try:
            tmp['params']['gain'] = float(self._gainTotal.text())
        except ValueError:
            dialogWarning('Could not read total gain! Setting to 0')
            tmp['params']['gain'] = 0
        
        return tmp
    
    def getParams(self):
        '''
        Get filter parameters for calculation of PID coeficients
        
        Returns:
            dict: parameters for filter design
        '''
        if self._sign.currentText() == 'Positive':
            sign = 1
        elif self._sign.currentText() == 'Negative':
            sign = -1
        ret = {
            'Type': 'DoubleIntLowpass',
            'ki': float(self._ki.text()),
            'kii': float(self._kii.text()),
            'Bounds': [float(self._boundsBtm.text()), float(self._boundsTop.text())],
            'Bounds integral': [float(self._intBoundsBtm.text()), float(self._intBoundsTop.text())],
            'Cutoff frequency [Hz]': float(self._freqCutoff.text()),
            'Filter order': float(self._filterOrder.text()),
            'Sampling frequency [Hz]': float(self._freqSampling),
            'Sign': sign,
            'Gain [dB]': float(self._gain.text())
        }
        if self.isDesigned():
            ret['Feedforward coefs'] = self._ff_coefs.tolist()
            ret['Feedback coefs'] = self._fb_coefs.tolist()

        return ret

    def setParams(self, params):
        '''
        Set filter parameters for calculation of PID coeficients
        
        Args:
            params: dict with filter parameters
        '''
        try:
            self._ki.setText('{:g}'.format(params['ki']))
            self._kii.setText('{:g}'.format(params['kii']))
            self._boundsBtm.setText('{:g}'.format(params['Bounds'][0]))
            self._boundsTop.setText('{:g}'.format(params['Bounds'][1]))
            self._intBoundsBtm.setText('{:g}'.format(params['Bounds integral'][0]))
            self._intBoundsTop.setText('{:g}'.format(params['Bounds integral'][1]))
            self._freqCutoff.setText('{:g}'.format(params['Cutoff frequency [Hz]']))
            self._filterOrder.setText('{:g}'.format(params['Filter order']))
            self._gain.setText('{:g}'.format(params['Gain [dB]']))
            self._freqSampling = params['Sampling frequency [Hz]']
            if params['Sign'] == 1:
                self._sign.setCurrentIndex(0)
            elif params['Sign'] == -1:
                self._sign.setCurrentIndex(1)
        except KeyError:
            dialogWarning('Could not read double loop filter parameters!')

class tabDoubleIntDoubleLowpass(QWidget):

    newDesign = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        # Variables
        self._coefs = {}
        self._freqSampling = 1
        self._ff_coefs1 = np.ones(1)
        self._fb_coefs1 = np.zeros(1)
        self._ff_coefs2 = np.ones(1)
        self._fb_coefs2 = np.zeros(1)

        # Flags
        self._flagFilterDesigned = False

        # Widgets
        # Integrator
        self._ki = QLineEdit('200')
        self._intBoundsBtm = QLineEdit('-inf')
        self._intBoundsTop = QLineEdit('inf')
        # Double integrator
        self._kii = QLineEdit('0')
        # Lowpass
        self._freqCutoff1 = QLineEdit('1')
        self._freqCutoff2 = QLineEdit('1')
        self._filterOrder1 = QLineEdit('1')
        self._filterOrder2 = QLineEdit('1')
        self._gain = QLineEdit('0')
        # General
        self._boundsBtm = QLineEdit('1e6')
        self._boundsTop = QLineEdit('100e6')
        self._sign = QComboBox()
        self._sign.addItem('Positive')
        self._sign.addItem('Negative')
        self._gainTotal = QLineEdit('0')
        
        self._btnDesign = QPushButton('Design')

        # Layout
        layout = QGridLayout()
        # Integrator settings
        layout.addWidget(QLabel('Integrator'), 0, 0)
        layout.addWidget(self._ki, 0, 1)
        layout.addWidget(QLabel('Integrators bounds'), 0, 2)
        layout.addWidget(self._intBoundsBtm, 0, 3)
        layout.addWidget(self._intBoundsTop, 0, 4)
        # Double integrator settings
        layout.addWidget(QLabel('Double integrator'), 1, 0)
        layout.addWidget(self._kii, 1, 1)
        # Bounds
        layout.addWidget(QLabel('Bounds'), 1, 2)
        layout.addWidget(self._boundsBtm, 1, 3)
        layout.addWidget(self._boundsTop, 1, 4)
        # Cutoff 1
        layout.addWidget(QLabel('Cutoff frequency 1 [Hz]'), 2, 0)
        layout.addWidget(self._freqCutoff1, 2, 1)
        # Order 1
        layout.addWidget(QLabel('Filter order 1'), 2, 2)
        layout.addWidget(self._filterOrder1, 2, 3, 1, 2)
        # Cutoff 2
        layout.addWidget(QLabel('Cutoff frequency 2 [Hz]'), 3, 0)
        layout.addWidget(self._freqCutoff2, 3, 1)
        # Order 2
        layout.addWidget(QLabel('Filter order 2'), 3, 2)
        layout.addWidget(self._filterOrder2, 3, 3, 1, 2)
        # Gain
        layout.addWidget(QLabel('Lowpass gain [dB]'), 4, 0)
        layout.addWidget(self._gain, 4, 1)
        # Total gain
        layout.addWidget(QLabel('Total gain [dB]'), 5, 0)
        layout.addWidget(self._gainTotal, 5, 1)
        # Sign
        layout.addWidget(QLabel('Filter sign'), 5, 2)
        layout.addWidget(self._sign, 5, 3)
        # Design btn
        layout.addWidget(self._btnDesign, 5, 4)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # UI
        self._btnDesign.clicked.connect(self._calcCoefs)

        # Return pressed
        self._ki.returnPressed.connect(self._calcCoefs)
        self._kii.returnPressed.connect(self._calcCoefs)
        self._boundsBtm.returnPressed.connect(self._calcCoefs)
        self._boundsTop.returnPressed.connect(self._calcCoefs)
        self._intBoundsBtm.returnPressed.connect(self._calcCoefs)
        self._intBoundsTop.returnPressed.connect(self._calcCoefs)
        self._freqCutoff1.returnPressed.connect(self._calcCoefs)
        self._filterOrder1.returnPressed.connect(self._calcCoefs)
        self._freqCutoff2.returnPressed.connect(self._calcCoefs)
        self._filterOrder2.returnPressed.connect(self._calcCoefs)
        self._gain.returnPressed.connect(self._calcCoefs)
        self._sign.activated.connect(self._calcCoefs)

    def isDesigned(self):
        '''
        Check if filter is already designed

        Returns:
            bool - if filter is designed
        '''
        if self._flagFilterDesigned:
            return True
        else:
            return False
    
    def setSampling(self, fSampling):
        '''
        Set sampling frequency
        
        Args:
            fSampling: sampling frequency
        '''
        self._freqSampling = fSampling

    def _calcCoefsIntegrator(self):
        '''
        Calculate PID filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        tmp = {}
        try:
            tmp['ki'] = float(self._ki.text())
            tmp['kii'] = float(self._kii.text())
            tmp['bounds'] = [
                float(self._boundsBtm.text()),
                float(self._boundsTop.text())
            ]
            tmp['int_bounds'] = [
                float(self._intBoundsBtm.text()),
                float(self._intBoundsTop.text())
            ]
        except ValueError:
            dialogWarning('Could not read integrator parameters!')
            return False

        self._coefs = tmp

        return True
    
    def _calcCoefsLowpass1(self):
        '''
        Calculate lowpass IIR filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        try:
            OmegaCutoff = 2*np.pi*float(self._freqCutoff1.text())
            gain_dB = float(self._gain.text())
            filterOrder = int(float(self._filterOrder1.text()))
        except ValueError:
            dialogWarning('Could not read lowpass 1 parameters!')
            return False

        # Check Nyquist frequency
        if OmegaCutoff >= np.pi*self._freqSampling:
            dialogWarning('Critical frequency 1 above Nyquist frequency!')
            return False
        # Check attenuations
        if filterOrder <= 0:
            dialogWarning('Filter order 1 must be positive')
            return False

        fb_coefs, ff_coefs, _ = fd.get_digital_filter_coefs(
            filterOrder,
            OmegaCutoff,
            2*np.pi*self._freqSampling
        )
        ff_coefs *= fd.dB_to_att(gain_dB)

        self._ff_coefs1 = ff_coefs
        self._fb_coefs1 = fb_coefs

        return True

    def _calcCoefsLowpass2(self):
        '''
        Calculate lowpass IIR filter coefficients

        Returns:
            bool - if procedure succeeded
        '''
        # Get filter params
        try:
            OmegaCutoff = 2*np.pi*float(self._freqCutoff2.text())
            gain_dB = float(self._gain.text())
            filterOrder = int(float(self._filterOrder2.text()))
        except ValueError:
            dialogWarning('Could not read lowpass 2 parameters!')
            return False

        # Check Nyquist frequency
        if OmegaCutoff >= np.pi*self._freqSampling:
            dialogWarning('Critical frequency 2 above Nyquist frequency!')
            return False
        # Check attenuations
        if filterOrder <= 0:
            dialogWarning('Filter order 2 must be positive')
            return False

        fb_coefs, ff_coefs, _ = fd.get_digital_filter_coefs(
            filterOrder,
            OmegaCutoff,
            2*np.pi*self._freqSampling
        )
        ff_coefs *= fd.dB_to_att(gain_dB)

        self._ff_coefs2 = ff_coefs
        self._fb_coefs2 = fb_coefs

        return True
    
    def _calcCoefs(self):

        if self._calcCoefsIntegrator():
            if self._calcCoefsLowpass1() and self._calcCoefsLowpass2():
                self._flagFilterDesigned = True
                print('Loop filter designed!', flush=True)
                self.newDesign.emit('DoubleIntDoubleLowpass')

    def filterCoefs(self):

        tmp = {
            'type': 'DoubleIntDoubleLowpass',
            'params': self._coefs
        }
        tmp['params']['ff_coefs1'] = self._ff_coefs1.tolist()
        tmp['params']['fb_coefs1'] = self._fb_coefs1.tolist()
        tmp['params']['ff_coefs2'] = self._ff_coefs2.tolist()
        tmp['params']['fb_coefs2'] = self._fb_coefs2.tolist()

        # Error calculation sign
        if self._sign.currentText() == 'Positive':
            tmp['params']['sign'] = 1
        elif self._sign.currentText() == 'Negative':
            tmp['params']['sign'] = -1

        # Total gain
        try:
            tmp['params']['gain'] = float(self._gainTotal.text())
        except ValueError:
            dialogWarning('Could not read total gain! Setting to 0')
            tmp['params']['gain'] = 0
        
        return tmp
    
    def getParams(self):
        '''
        Get filter parameters for calculation of PID coeficients
        
        Returns:
            dict: parameters for filter design
        '''
        if self._sign.currentText() == 'Positive':
            sign = 1
        elif self._sign.currentText() == 'Negative':
            sign = -1
        ret = {
            'Type': 'DoubleIntDoubleLowpass',
            'ki': float(self._ki.text()),
            'kii': float(self._kii.text()),
            'Bounds': [float(self._boundsBtm.text()), float(self._boundsTop.text())],
            'Bounds integral': [float(self._intBoundsBtm.text()), float(self._intBoundsTop.text())],
            'Cutoff frequency 1 [Hz]': float(self._freqCutoff1.text()),
            'Filter order 1': float(self._filterOrder1.text()),
            'Cutoff frequency 2 [Hz]': float(self._freqCutoff2.text()),
            'Filter order 2': float(self._filterOrder2.text()),
            'Sampling frequency [Hz]': float(self._freqSampling),
            'Sign': sign,
            'Gain [dB]': float(self._gain.text())
        }
        if self.isDesigned():
            ret['Feedforward coefs 1'] = self._ff_coefs1.tolist()
            ret['Feedback coefs 1'] = self._fb_coefs1.tolist()
            ret['Feedforward coefs 2'] = self._ff_coefs2.tolist()
            ret['Feedback coefs 2'] = self._fb_coefs2.tolist()

        return ret

    def setParams(self, params):
        '''
        Set filter parameters for calculation of PID coeficients
        
        Args:
            params: dict with filter parameters
        '''
        try:
            self._ki.setText('{:g}'.format(params['ki']))
            self._kii.setText('{:g}'.format(params['kii']))
            self._boundsBtm.setText('{:g}'.format(params['Bounds'][0]))
            self._boundsTop.setText('{:g}'.format(params['Bounds'][1]))
            self._intBoundsBtm.setText('{:g}'.format(params['Bounds integral'][0]))
            self._intBoundsTop.setText('{:g}'.format(params['Bounds integral'][1]))
            self._freqCutoff1.setText('{:g}'.format(params['Cutoff frequency 1 [Hz]']))
            self._filterOrder1.setText('{:g}'.format(params['Filter order 1']))
            self._freqCutoff2.setText('{:g}'.format(params['Cutoff frequency 2 [Hz]']))
            self._filterOrder2.setText('{:g}'.format(params['Filter order 2']))
            self._gain.setText('{:g}'.format(params['Gain [dB]']))
            self._freqSampling = params['Sampling frequency [Hz]']
            if params['Sign'] == 1:
                self._sign.setCurrentIndex(0)
            elif params['Sign'] == -1:
                self._sign.setCurrentIndex(1)
        except KeyError:
            dialogWarning('Could not read double loop filter parameters!')


class FiltersWidget(QTabWidget):

    newFilterDesigned = pyqtSignal(dict)

    def __init__(self):

        super().__init__()

        self._currentFilter = 'IntLowpass'

        self._tabIntLowpass = tabIntLowpass()
        self._tabDoubleIntLowpass = tabDoubleIntLowpass()
        self._tabDoubleIntDoubleLowpass = tabDoubleIntDoubleLowpass()

        self._tabIntLowpass.newDesign.connect(self.catchNewDesign)
        self._tabDoubleIntLowpass.newDesign.connect(self.catchNewDesign)
        self._tabDoubleIntDoubleLowpass.newDesign.connect(self.catchNewDesign)

        self.addTab(self._tabIntLowpass, 'IntLowpass')
        self.addTab(self._tabDoubleIntLowpass, 'DoubleIntLowpass')
        self.addTab(self._tabDoubleIntDoubleLowpass, 'DoubleIntDoubleLowpass')


        self._tabs = {
            'IntLowpass': self._tabIntLowpass,
            'DoubleIntLowpass': self._tabDoubleIntLowpass,
            'DoubleIntDoubleLowpass': self._tabDoubleIntDoubleLowpass
        }

    def isDesigned(self, filterType):

        return self._tabs['filterType'].isDesigned()

    def catchNewDesign(self, filterType):

        self._currentFilter = filterType

    def setSampling(self, fSampling):
        '''
        Set sampling frequency
        
        Args:
            fSampling: sampling frequency
        '''
        for key in self._tabs.keys():
            try:
                self._tabs[key].setSampling(fSampling)
            except:
                pass
        # self._tabLowpass.setSampling(fSampling)
        # self._tabLoopFreq.setSampling(fSampling)
        # self._tabLoopPhase.setSampling(fSampling)

    def filterCoefs(self):
        '''
        Get last designed filter coefficients
        
        Returns:
            dict: filter coefs. Return empty dict if failed
        '''
        # Loop filter
        if not self._tabs[self._currentFilter].isDesigned():
            dialogWarning('Design loop filter first!')
            return {}
        else:
            return self._tabs[self._currentFilter].filterCoefs()

    def _emitNewDesign(self, filterType):
        '''
        Emit signal newFilterDesigned
        
        Args:
            filterType: type of filter
        '''
        tmp = self.filterCoefs(filterType)
        self.newFilterDesigned.emit(tmp)

    def getParams(self):
        '''
        Get filters parameters. Used when exporting settings
        
        Returns:
            dict: nested dictionary with parameters for filters design
        '''
        ret = {}
        for key in self._tabs.keys():
            ret[key] = self._tabs[key].getParams()

        return ret

    def setParams(self, params):
        '''
        Set filters parameters. Used when importing settings
        
        Args:
            dict: nested dictionary with parameters for filters design
        '''
        for key in params.keys():
            try:
                self._tabs[key].setParams(params[key])
            except KeyError:
                print('Unknown filter type {}!'.format(key))
        # # Lowpass
        # if 'lowpass' in params.keys():
        #     try:
        #         self._tabs['lowpass'].setParams(params['lowpass'])
        #     except KeyError as e:
        #         print('Could not set lowpass filter parameters! {}'.format(e), flush=True)
        # else:
        #     print('Could not find parameters for lowpass filter', flush=True)
        # # Loop frequency filter
        # if 'loop-freq' in params.keys():
        #     if params['loop-freq']['Type'] != cfg.loopFilter:
        #         print('Could not find parameters for frequency loop filter', flush=True)
        #     else:
        #         try:
        #             self._tabs['loop-freq'].setParams(params['loop-freq'])
        #         except Exception as e:
        #             print('Could not set parameters for frequency loop filter! {}'.format(e), flush=True)
        # else:
        #     print('Could not find parameters for frequency loop filter!', flush=True)
        # # Loop phase filter
        # if 'loop-phase' in params.keys():
        #     if params['loop-phase']['Type'] != cfg.loopFilter:
        #         print('Could not find parameters for phase loop filter', flush=True)
        #     else:
        #         try:
        #             self._tabs['loop-phase'].setParams(params['loop-phase'])
        #         except Exception as e:
        #             print('Could not set parameters for phase loop filter! {}'.format(e), flush=True)
        # else:
        #     print('Could not find parameters for phase loop filter!', flush=True)
        
