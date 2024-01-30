# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
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
        self._labelCutoff = QLabel('0')
        self._labelOrder = QLabel('0')

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
        layout.addWidget(QLabel('Cutoff frequency [Hz]'), 3, 0)
        layout.addWidget(self._labelCutoff, 3, 1)
        layout.addWidget(QLabel('Filter order'), 3, 2)
        layout.addWidget(self._labelOrder, 3, 3)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # UI
        self._btnDesign.clicked.connect(self._calcCoefs)

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
            gain = float(self._gain.text())
            attPassband = fd.dB_to_att(float(self._attPassband.text()) - gain)
            attStopband = fd.dB_to_att(float(self._attStopband.text()) - gain)
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
        if attPassband <= attStopband:
            dialogWarning('Passband attenuation below stopband attenuation!')
            return False

        # Order
        N = fd.calc_order(OmegaPassband, OmegaStopband, attPassband, attStopband)
        self._labelOrder.setText('{}'.format(N))
        # Cutoff frequency
        OmegaCutoff = fd.calc_cutoff_freq(OmegaPassband, attPassband, N)
        self._labelCutoff.setText('{:.2e}'.format(OmegaCutoff/2/np.pi))

        fb_coefs, ff_coefs, _ = fd.get_digital_filter_coefs(
            N,
            OmegaCutoff,
            2*np.pi*self._freqSampling
        )
        ff_coefs *= fd.dB_to_att(gain)

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
        return self._ff_coefs, self._fb_coefs

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
        # Button
        layout.addWidget(self._btnDesign, 3, 2, 1, 3)

        mainLayout = QVBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # UI
        self._btnDesign.clicked.connect(self._calcCoefs)

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

    def filterCoefs(self):
        '''
        Get PID filter coefficients
        
        Returns:
            dict: PID filter coefficients
        '''
        return self._coefs
               
    def getParams(self):
        '''
        Get filter parameters for calculation of PID coeficients
        
        Returns:
            dict: parameters for filter design
        '''
        ret = {
            'kp': float(self._kp.text()),
            'ki': float(self._ki.text()),
            'kd': float(self._kd.text()),
            'Gain': float(self._gain.text()),
            'Bounds': [float(self._boundsBtm.text()), float(self._boundsTop.text())],
            'Bounds integral': [float(self._intBoundsBtm.text()), float(self._intBoundsTop.text())],
            'Lead coef': float(self._leadCoef.text())
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
        except KeyError:
            dialogWarning('Could not read PID filter parameters!')


class FiltersWidget(QTabWidget):

    newFilterDesigned = pyqtSignal(dict)

    def __init__(self):

        super().__init__()

        self._tabPID = tabPID()
        self._tabLowpass = tabLowpass()

        self.addTab(self._tabPID, 'PID')
        self.addTab(self._tabLowpass, 'lowpass')

        self._tabLowpass.newDesign.connect(lambda : self._emitNewDesign('lowpass'))
        self._tabPID.newDesign.connect(lambda: self._emitNewDesign('pid'))

    def setSampling(self, fSampling):
        '''
        Set sampling frequency
        
        Args:
            fSampling: sampling frequency
        '''
        self._tabLowpass.setSampling(fSampling)

    def filterCoefs(self, filterType):
        '''
        Get filter coefficients based on filterType
        
        Args:
            filterType: type of filter ('lowpass' or 'pid')
        Returns:
            dict: filter coefs. Return empty dict if failed
        '''
        if filterType == 'lowpass':
            if not self._tabLowpass.isDesigned():
                dialogWarning('Design filter first!')
                return {}
            else:
                ff_coefs, fb_coefs = self._tabLowpass.filterCoefs()
                return {'ff_coefs': ff_coefs, 'fb_coefs': fb_coefs}
        if filterType == 'pid':
            if not self._tabPID.isDesigned():
                dialogWarning('Design filter first!')
                return {}
            else:
                return self._tabPID.filterCoefs()

    def _emitNewDesign(self, filterType):
        '''
        Emit signal newFilterDesigned
        
        Args:
            filterType: type of filter ('lowpass' or 'pid')
        '''
        tmp = {'filterType': filterType}
        tmp['params'] = self.filterCoefs(filterType)
        self.newFilterDesigned.emit(tmp)

    def getParams(self):
        '''
        Get filters parameters. Used when exporting settings
        
        Returns:
            dict: nested dictionary with parameters for filters design
        '''
        ret = {}
        ret['PID'] = self._tabPID.getParams()
        ret['Lowpass'] = self._tabLowpass.getParams()

        return ret

    def setParams(self, params):
        '''
        Set filters parameters. Used when importing settings
        
        Args:
            dict: nested dictionary with parameters for filters design
        '''
        self._tabPID.setParams(params['PID'])
        self._tabLowpass.setParams(params['Lowpass'])
