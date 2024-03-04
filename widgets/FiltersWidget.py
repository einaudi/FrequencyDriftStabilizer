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
            self._freqPassband.setText('{}'.format(params['Passband frequency [Hz]']))
            self._freqStopband.setText('{}'.format(params['Stopband frequency [Hz]']))
            self._attPassband.setText('{}'.format(params['Passband attenuation [dB]']))
            self._attStopband.setText('{}'.format(params['Stopband attenuation [dB]']))
            self._gain.setText('{}'.format(params['Gain [dB]']))
            self._freqSampling = params['Sampling frequency [Hz]']
        except KeyError:
            dialogWarning('Could not read lowpass filter parameters!')


class tabPID(QWidget):

    newDesign = pyqtSignal()

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
            tmp['bounds'] = (
                float(self._boundsBtm.text()),
                float(self._boundsTop.text())
            )
            tmp['int_bounds'] = (
                float(self._intBoundsBtm.text()),
                float(self._intBoundsTop.text())
            )
            tmp['lead_coef'] = float(self._leadCoef.text())
        except ValueError:
            dialogWarning('Could not read parameters!')
            return False

        self._flagFilterDesigned = True
        print('PID filter designed!', flush=True)
        dialogInformation('PID filter designed successfully!')

        self._coefs = tmp
        self.newDesign.emit()

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

    def filterCoefs(self, filterType='pid'):
        '''
        Get PID filter coefficients
        
        Returns:
            dict: PID filter coefficients
        '''
        ret = {
            'type': filterType,
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
            self._kp.setText('{:.4e}'.format(params['kp']))
            self._ki.setText('{:.4e}'.format(params['ki']))
            self._kd.setText('{:.4e}'.format(params['kd']))
            self._gain.setText('{:.4}'.format(params['Gain']))
            self._boundsBtm.setText('{:.4e}'.format(params['Bounds'][0]))
            self._boundsTop.setText('{:.4e}'.format(params['Bounds'][1]))
            self._intBoundsBtm.setText('{:.4e}'.format(params['Bounds integral'][0]))
            self._intBoundsTop.setText('{:.4e}'.format(params['Bounds integral'][1]))
            self._leadCoef.setText('{:.4}'.format(params['Lead coef']))
            if params['Sign'] == 1:
                self._sign.setCurrentIndex(0)
            elif params['Sign'] == -1:
                self._sign.setCurrentIndex(1)
        except KeyError:
            dialogWarning('Could not read PID filter parameters!', flush=True)


class tabLoop(QWidget):

    newDesign = pyqtSignal()

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
        
        self._btnDesign = QPushButton('Design')

        # Layout
        layout = QGridLayout()
        # Integrator settings
        layout.addWidget(QLabel('Integrator coefficient'), 0, 0, 1, 2)
        layout.addWidget(self._ki, 0, 2)
        layout.addWidget(QLabel('Integrator bounds'), 0, 3, 1, 2)
        layout.addWidget(self._intBoundsBtm, 0, 5)
        layout.addWidget(self._intBoundsTop, 0, 6)
        # Cutoff
        layout.addWidget(QLabel('Cutoff frequency [Hz]'), 1, 0, 1, 2)
        layout.addWidget(self._freqCutoff, 1, 2)
        layout.addWidget(QLabel('Filter order'), 1, 3, 1, 2)
        layout.addWidget(self._filterOrder, 1, 5)
        # Gain
        layout.addWidget(QLabel('Lowpass gain [dB]'), 3, 0)
        layout.addWidget(self._gain, 3, 1)
        # Sign
        layout.addWidget(QLabel('Filter sign'), 3, 2)
        layout.addWidget(self._sign, 3, 3)
        # Bounds
        layout.addWidget(QLabel('Bounds'), 3, 4)
        layout.addWidget(self._boundsBtm, 3, 5)
        layout.addWidget(self._boundsTop, 3, 6)
        # Design btn
        layout.addWidget(self._btnDesign, 4, 5, 1, 2)

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
            tmp['bounds'] = (
                float(self._boundsBtm.text()),
                float(self._boundsTop.text())
            )
            tmp['int_bounds'] = (
                float(self._intBoundsBtm.text()),
                float(self._intBoundsTop.text())
            )
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

        print('Loop filter designed!', flush=True)

        msg = 'Loop filter designed successfully!\n'
        msg += 'Order: {}\n'.format(filterOrder)
        msg += 'Cutoff frequency {:.2e} Hz\n'.format(OmegaCutoff/2/np.pi)
        dialogInformation(msg)

        return True
    
    def _calcCoefs(self):

        if self._calcCoefsIntegrator():
            if self._calcCoefsLowpass():
                self._flagFilterDesigned = True
                self.newDesign.emit()

    def filterCoefs(self, filterType='loop'):

        tmp = {
            'type': filterType,
            'params': self._coefs
        }
        tmp['params']['ff_coefs'] = self._ff_coefs
        tmp['params']['fb_coefs'] = self._fb_coefs

        # Error calculation sign
        if self._sign.currentText() == 'Positive':
            tmp['params']['sign'] = 1
        elif self._sign.currentText() == 'Negative':
            tmp['params']['sign'] = -1
        
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
            self._ki.setText('{:.4e}'.format(params['ki']))
            self._boundsBtm.setText('{:.4e}'.format(params['Bounds'][0]))
            self._boundsTop.setText('{:.4e}'.format(params['Bounds'][1]))
            self._intBoundsBtm.setText('{:.4e}'.format(params['Bounds integral'][0]))
            self._intBoundsTop.setText('{:.4e}'.format(params['Bounds integral'][1]))
            self._freqCutoff.setText('{}'.format(params['Cutoff frequency [Hz]']))
            self._filterOrder.setText('{}'.format(params['Filter order']))
            self._gain.setText('{}'.format(params['Gain [dB]']))
            self._freqSampling = params['Sampling frequency [Hz]']
            if params['Sign'] == 1:
                self._sign.setCurrentIndex(0)
            elif params['Sign'] == -1:
                self._sign.setCurrentIndex(1)
        except KeyError:
            dialogWarning('Could not read loop filter parameters!')


class tabLoopDouble(QWidget):

    newDesign = pyqtSignal()

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
        
        self._btnDesign = QPushButton('Design')

        # Layout
        layout = QGridLayout()
        # Integrator settings
        layout.addWidget(QLabel('Integrator coefficient'), 0, 0)
        layout.addWidget(self._ki, 0, 1)
        layout.addWidget(QLabel('Integrators bounds'), 0, 2)
        layout.addWidget(self._intBoundsBtm, 0, 3)
        layout.addWidget(self._intBoundsTop, 0, 4)
        # Double integrator settings
        layout.addWidget(QLabel('Double integrator coefficient'), 1, 0)
        layout.addWidget(self._kii, 1, 1)
        # Bounds
        layout.addWidget(QLabel('Bounds'), 1, 2)
        layout.addWidget(self._boundsBtm, 1, 3)
        layout.addWidget(self._boundsTop, 1, 4)
        # Cutoff
        layout.addWidget(QLabel('Cutoff frequency [Hz]'), 2, 0)
        layout.addWidget(self._freqCutoff, 2, 1)
        # Gain
        layout.addWidget(QLabel('Lowpass gain [dB]'), 2, 2)
        layout.addWidget(self._gain, 2, 3, 1, 2)
        # Order
        layout.addWidget(QLabel('Filter order'), 3, 0)
        layout.addWidget(self._filterOrder, 3, 1)
        # Sign
        layout.addWidget(QLabel('Filter sign'), 3, 2)
        layout.addWidget(self._sign, 3, 3)
        # Design btn
        layout.addWidget(self._btnDesign, 3, 4)

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
            tmp['bounds'] = (
                float(self._boundsBtm.text()),
                float(self._boundsTop.text())
            )
            tmp['int_bounds'] = (
                float(self._intBoundsBtm.text()),
                float(self._intBoundsTop.text())
            )
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

        print('Loop filter designed!', flush=True)

        msg = 'Double loop filter designed successfully!\n'
        msg += 'Order: {}\n'.format(filterOrder)
        msg += 'Cutoff frequency {:.2e} Hz\n'.format(OmegaCutoff/2/np.pi)
        dialogInformation(msg)

        return True
    
    def _calcCoefs(self):

        if self._calcCoefsIntegrator():
            if self._calcCoefsLowpass():
                self._flagFilterDesigned = True
                self.newDesign.emit()

    def filterCoefs(self, filterType='loop'):

        tmp = {
            'type': filterType,
            'params': self._coefs
        }
        tmp['params']['ff_coefs'] = self._ff_coefs
        tmp['params']['fb_coefs'] = self._fb_coefs

        # Error calculation sign
        if self._sign.currentText() == 'Positive':
            tmp['params']['sign'] = 1
        elif self._sign.currentText() == 'Negative':
            tmp['params']['sign'] = -1
        
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
            self._ki.setText('{:.4e}'.format(params['ki']))
            self._boundsBtm.setText('{:.4e}'.format(params['Bounds'][0]))
            self._boundsTop.setText('{:.4e}'.format(params['Bounds'][1]))
            self._intBoundsBtm.setText('{:.4e}'.format(params['Bounds integral'][0]))
            self._intBoundsTop.setText('{:.4e}'.format(params['Bounds integral'][1]))
            self._freqCutoff.setText('{}'.format(params['Cutoff frequency [Hz]']))
            self._filterOrder.setText('{}'.format(params['Filter order']))
            self._gain.setText('{}'.format(params['Gain [dB]']))
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

        self._tabLoopFreq = tabLoop()
        self._tabLoopPhase = tabLoop()
        self._tabLoopDoubleFreq = tabLoopDouble()
        self._tabLoopDoublePhase = tabLoopDouble()
        self._tabPIDfreq = tabPID()
        self._tabPIDphase = tabPID()
        self._tabLowpass = tabLowpass()

        self.addTab(self._tabLoopFreq, 'Loop freq')
        self.addTab(self._tabLoopPhase, 'Loop phase')
        self.addTab(self._tabLoopDoubleFreq, 'Double loop freq')
        self.addTab(self._tabLoopDoublePhase, 'Double loop phase')
        # self.addTab(self._tabPIDfreq, 'PID freq')
        # self.addTab(self._tabPIDphase, 'PID phase')
        self.addTab(self._tabLowpass, 'lowpass')

        self._tabLowpass.newDesign.connect(lambda : self._emitNewDesign('lowpass'))

        self._tabs = {
            'lowpass': self._tabLowpass,
            'loop-freq': self._tabLoopFreq,
            'loop-phase': self._tabLoopPhase,
            'loopDouble-freq': self._tabLoopDoubleFreq,
            'loopDouble-phase': self._tabLoopDoublePhase
            # 'pid-freq': self._tabPIDfreq,
            # 'pid-phase': self._tabPIDphase
        }

    def isDesigned(self, filterType):

        return self._tabs['filterType'].isDesigned()

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

    def filterCoefs(self, filterType):
        '''
        Get filter coefficients based on filterType
        
        Args:
            filterType: type of filter ('lowpass', 'pid-freq', 'pid-phase')
        Returns:
            dict: filter coefs. Return empty dict if failed
        '''
        if filterType == 'lowpass':
            if not self._tabLowpass.isDesigned():
                dialogWarning('Design filter first!')
                return {}
            else:
                return self._tabLowpass.filterCoefs()
        # PID
        elif filterType == 'pid-freq':
            if not self._tabPIDfreq.isDesigned():
                dialogWarning('Design frequency PID filter first!')
                return {}
            else:
                return self._tabPIDfreq.filterCoefs('pid-freq')
        elif filterType == 'pid-phase':
            if not self._tabPIDphase.isDesigned():
                dialogWarning('Design phase PID filter first!')
                return {}
            else:
                return self._tabPIDphase.filterCoefs('pid-phase')
        # Loop
        elif filterType == 'loop-freq':
            if not self._tabLoopFreq.isDesigned():
                dialogWarning('Design frequency loop filter first!')
                return {}
            else:
                return self._tabLoopFreq.filterCoefs('loop-freq')
        elif filterType == 'loop-phase':
            if not self._tabLoopPhase.isDesigned():
                dialogWarning('Design phase loop filter first!')
                return {}
            else:
                return self._tabLoopPhase.filterCoefs('loop-phase')
        # Double loop
        elif filterType == 'loopDouble-freq':
            if not self._tabLoopDoubleFreq.isDesigned():
                dialogWarning('Design frequency loop filter first!')
                return {}
            else:
                return self._tabLoopDoubleFreq.filterCoefs('loopDouble-freq')
        elif filterType == 'loopDouble-phase':
            if not self._tabLoopDoublePhase.isDesigned():
                dialogWarning('Design phase loop filter first!')
                return {}
            else:
                return self._tabLoopDoublePhase.filterCoefs('loopDouble-phase')

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
        # ret['loop-freq'] = self._tabLoopFreq.getParams()
        # ret['loop-phase'] = self._tabLoopPhase.getParams()
        # ret['pid-freq'] = self._tabPIDfreq.getParams()
        # ret['pid-phase'] = self._tabPIDphase.getParams()
        # ret['lowpass'] = self._tabLowpass.getParams()

        return ret

    def setParams(self, params):
        '''
        Set filters parameters. Used when importing settings
        
        Args:
            dict: nested dictionary with parameters for filters design
        '''
        for filterType in self._tabs.keys():
            try:
                self._tabs[filterType].setParams(params[filterType])
            except KeyError as e:
                print('Could not find parameters for filter {}'.format(e), flush=True)
