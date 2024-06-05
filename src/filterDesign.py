# -*- coding: utf-8 -*-

import numpy as np

from scipy.signal import iirfilter, freqz


# Conversions
def att_to_dB(att):

    return 10*np.log10(att)

def dB_to_att(A):

    ret = A/10.
    ret = np.power(10., ret)

    return ret

def dB_to_att_intensity(A):

    ret = A/20.
    ret = np.power(10., ret)

    return ret

def warp_frequency(omega_pre, f_samp):

    return 2*np.arctan(0.5*omega_pre/f_samp)

def prewarp_frequency(omega, f_samp):

    return 2*f_samp * np.tan(omega/2)


# Initial calculations
def calc_order(Omega_p, Omega_s, att_p, att_s, btype='lowpass', mode='Butterworth'):

    # frequency mapping
    Omega_p_map = map_frequency(Omega_p, 1, btype)
    Omega_s_map = map_frequency(Omega_s, 1, btype)

    if mode == 'Butterworth':
        nom = np.power(att_s, -2) - 1
        nom /= np.power(att_p, -2) - 1
        nom = np.log10(nom)

        denom = Omega_s_map/Omega_p_map
        denom = 2*np.log10(denom)

        ret = nom/denom
        ret = np.ceil(ret)

        return int(ret)
    else:
        print('Order calculation. Unknown filter type.')
        return None
    
def calc_cutoff_freq(Omega, att, order, btype='lowpass', mode='Butterworth'):

    if mode == 'Butterworth':
        if btype == 'lowpass':
            ret = np.power(att, -2) - 1
            ret = np.power(ret, 1/2/order)
            ret = Omega/ret
        elif btype == 'highpass':
            ret = np.power(att, -2) - 1
            ret = np.power(ret, 1/2/order)
            ret = Omega*ret

        return ret
    else:
        print('Cutoff frequency calculation. Unknown filter type.')
        return None


# Frequency mapping to different band types
def map_frequency(Omega, Omega_c, btype='lowpass'):

    if btype == 'lowpass':
        return Omega
    elif btype == 'highpass':
        return Omega_c/Omega
    else:
        return 0


# Normalised filter calculations
def calc_normalised_lowpass_roots(order):

    ret = []
    N = int(order)
    for k in range(N):
        coef = (2.*k+N+1)/N
        ret.append(np.exp(0.5j*np.pi*coef))

    return ret

def get_continuous_transfer_function(Omega_c, order, sk, btype='lowpass'):

    N = int(order)
    def H(s):
        if btype == 'lowpass':
            s_coef = s/Omega_c
        elif btype == 'highpass':
            s_coef = Omega_c/s
        ret = 1
        for k in range(N):
            ret /= (s_coef - sk[k])

        return ret
    
    return H

def get_digital_transfer_function(Omega_c, order, sk, f_samp, btype='lowpass'):

    N = int(order)
    # def H(z):
    #     z_coef = (1-1/z)/(1+1/z) * 2*f_samp
    #     ret = np.power(Omega_c, N)
    #     for k in range(N):
    #         ret /= (z_coef - sk[k]*Omega_c)

    #     return ret

    continuous_filter = get_continuous_transfer_function(Omega_c, N, sk, btype)

    def H(z):
        z_coef = (1-1/z)/(1+1/z) * 2*f_samp
        return continuous_filter(z_coef)
    
    return H


# Digital filter parameters
def get_digital_filter_coefs(order, omega_c, omega_samp, btype='lowpass'):

    N = int(order)
    omega_nyquist = omega_samp/2
    Wn = omega_c / omega_nyquist # normalise frequency to nyquist frequency

    b, a = iirfilter(N, Wn, btype=btype)

    w, h = freqz(
        b,
        a
    )

    ff_coefs = b / a[0]
    fb_coefs = a / a[0]
    fb_coefs = -fb_coefs[1:]

    return fb_coefs, ff_coefs, [w, h]

def get_digital_filter_zpk(order, omega_c, omega_samp, btype='lowpass'):

    N = int(order)
    omega_nyquist = omega_samp/2
    Wn = omega_c / omega_nyquist # normalise frequency to nyquist frequency

    z, p, k = iirfilter(N, Wn, btype=btype, output='zpk')

    return z, p, k
