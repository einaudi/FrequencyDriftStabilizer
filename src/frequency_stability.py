# -*- coding: utf-8 -*-

import numpy as np


# ----- Misc -----
def calc_fractional_frequency(fs, f0):

    ret = fs - f0
    ret /= f0

    # print(ret)

    return ret

def calc_phase_error(fs_frac, f_sampling):

    ret = np.cumsum(fs_frac)
    ret /= f_sampling

    # print(ret)

    return ret

def calc_array_avg(arr, tau, f_sampling):

    n = tau * f_sampling # averaging factor
    n = int(np.floor(n)) + 1
    loop_count = arr.size / n
    loop_count = int(np.floor(loop_count))

    ret = []
    iter = 0
    for _ in range(loop_count):
        ret.append(np.average(arr[iter:iter+n]))
        iter += n

    return np.array(ret)

def calc_array_diff(arr):

    N = arr.size
    ret = arr[1:N] - arr[:N-1]

    return ret

# ----- Deviations -----
def calc_ADEV_single(phase_error, tau):

    N = phase_error.size

    ret = 0
    for i in range(N-2):
        tmp = phase_error[i+2]
        tmp -= 2*phase_error[i+1]
        tmp += phase_error[i]

        ret += np.power(tmp, 2)

    ret /= (2*(N - 2)*np.power(tau, 2))
    ret = np.sqrt(ret)

    return ret

def calc_ADEV(phase_error, taus):

    ret = []
    print('Calculating Allan deviation...')
    for tau in taus:
        ret.append(calc_ADEV_single(phase_error, tau))


    return np.array(ret)

def calc_ADEV_overlapped_single(phase_error, tau, f_sampling):

    N = phase_error.size
    n = tau * f_sampling # averaging factor
    n = int(np.floor(n))
    # print(N, n, flush=True)

    ret = 0
    for i in range(N - 2*n):
        tmp = phase_error[i + 2*n]
        tmp -= 2*phase_error[i+n]
        tmp += phase_error[i]

        ret += np.power(tmp, 2)
    # print(ret, (2*(N - 2*n)*np.power(tau, 2)), flush=True)
    ret /= (2*(N - 2*n)*np.power(tau, 2))
    ret = np.sqrt(ret)

    return ret

def calc_ADEV_overlapped(phase_error, taus, f_sampling):

    ret = []
    print('Calculating overlapped Allan deviation...')
    
    for tau in taus:
        ret.append(calc_ADEV_overlapped_single(phase_error, tau, f_sampling))

    return np.array(ret)

def calc_HDEV_single(phase_error, tau, f_sampling):

    N = phase_error.size
    n = tau * f_sampling # averaging factor
    n = int(np.floor(n))

    ret = 0
    for i in range(N - 3*n):
        tmp = phase_error[i + 3*n]
        tmp -= 3*phase_error[i+2*n]
        tmp += 3*phase_error[i+n]
        tmp -= phase_error[i]

        ret += np.power(tmp, 2)

    ret /= (6*(N - 3*n)*np.power(tau, 2))
    ret = np.sqrt(ret)

    return ret

def calc_HDEV(phase_error, taus, f_sampling):

    ret = []
    print('Calculating Hadamard deviation...')
    for tau in taus:
        ret.append(calc_HDEV_single(phase_error, tau, f_sampling))

    return np.array(ret)

# ----- Confidence intervals and noise type -----
def calc_r1(fs_frac):

    f_avg = np.average(fs_frac)
    N = fs_frac.size
    nom = 0
    denom = 0

    # Numerator
    for i in range(N-1):
        nom += (fs_frac[i] - f_avg) * (fs_frac[i+1] - f_avg)
    # Denominator
    for i in range(N):
        denom += np.power(fs_frac[i] - f_avg, 2)

    ret = nom/denom

    return ret

def calc_noise_type(arr_avg):

    flag = True
    d = 0
    ret = 0
    z = arr_avg

    while(flag):
        r1 = calc_r1(z)
        delta = r1/(r1+1)

        if (delta < .25):
            p = -2*(delta + d)
            ret = p # for frequency data
            flag = False
        else:
            z = calc_array_diff(z)
            d += 1

    return ret

def calc_noise_id_single(freqs, tau, f_sampling):

    tmp = calc_array_avg(freqs, tau, f_sampling)
    ret = calc_noise_type(tmp)

    return ret

def calc_noise_id(freqs, taus, f_sampling):

    ret = []

    for tau in taus:
        ret.append(calc_noise_id_single(freqs, tau, f_sampling))

    return np.array(ret)

def calc_confidence_interval_single(dev, tau, f_sampling, noiseID, N):

    avgCount = tau * f_sampling
    loopCount = N/avgCount # number of loop iterations
    loopCount_reduced = np.sqrt(loopCount)

    # dominant white PM noise
    if noiseID >= 1.5:
        tmp = .99 * dev/loopCount_reduced
    # dominant flicker PM noise
    elif noiseID < 1.5 and noiseID >= .5:
        tmp = .99 * dev/loopCount_reduced
    # dominant white FM noise
    elif noiseID < .5 and noiseID >= -.5:
        tmp = .87 * dev/loopCount_reduced
    # dominant flicker FM noise
    elif noiseID < -.5 and noiseID >= -1.5:
        tmp = .77 * dev/loopCount_reduced
    # dominant random walk FM noise
    else:
        tmp = .75 * dev/loopCount_reduced

    return tmp

def calc_confidence_interval(devs, taus, f_sampling, noiseIDs, N):

    ret = []
    for i in range(devs.size):
        ret.append(calc_confidence_interval_single(devs[i], taus[i], f_sampling, noiseIDs[i], N))

    return np.array(ret)

def dominant_noise_single(noiseID):

    # dominant white PM noise
    if noiseID >= 1.5:
        ret = 'white PM'
    # dominant flicker PM noise
    elif noiseID < 1.5 and noiseID >= .5:
        ret = 'flicker PM'
    # dominant white FM noise
    elif noiseID < .5 and noiseID >= -.5:
        ret = 'white FM'
    # dominant flicker FM noise
    elif noiseID < -.5 and noiseID >= -1.5:
        ret = 'flicker FM'
    # dominant random walk FM noise
    else:
        ret = 'random walk FM'

    return ret

def dominant_noise(noiseIDs):

    ret = []

    for noiseID in noiseIDs:
        ret.append(dominant_noise_single(noiseID))

    return ret

if __name__ == '__main__':

    from utils import read_csv
    import matplotlib.pyplot as plt

    data, meta = read_csv('./sample_Data_5000.csv')

    freqs = data['Frequency [Hz]']

    f_sampling = meta['Sampling frequency [Hz]']

    N = freqs.size
    T = N / f_sampling

    fs_frac = calc_fractional_frequency(freqs, meta['Central frequency [Hz]'])
    phase_error = calc_phase_error(fs_frac, f_sampling)

    taus = np.linspace(
        1/(f_sampling+1),
        0.49*T,
        20
    )

    # Deviations
    adevs = calc_ADEV(phase_error, taus)
    adevs_overlapped = calc_ADEV_overlapped(phase_error, taus, f_sampling)
    hdevs = calc_HDEV(phase_error, taus, f_sampling)

    # Noise type and confidence interval
    alphas = calc_noise_id(freqs, taus, f_sampling)
    conf_int_adev = calc_confidence_interval(adevs, taus, f_sampling, alphas, N)
    conf_int_adev_overlapped = calc_confidence_interval(adevs_overlapped, taus, f_sampling, alphas, N)
    conf_int_hdev = calc_confidence_interval(hdevs, taus, f_sampling, alphas, N)

    noise_dom = dominant_noise(alphas)
    print('Dominant noise: ', noise_dom)

    # Plotting
    fig = plt.figure(dpi=150)

    ax1 = fig.add_subplot(311)
    ax2 = fig.add_subplot(312)
    ax3 = fig.add_subplot(313)

    ax1.set_ylabel('frequency [Hz]')
    ax2.set_ylabel('f_frac [Hz]')
    ax3.set_ylabel('phase_error [rad]')
    ax3.set_xlabel('Time [a.u.]')
    ax3.set_yscale('log')

    ax1.plot(
        freqs
    )

    ax2.plot(
        fs_frac
    )
    ax3.plot(
        phase_error
    )
    

    plt.tight_layout()
    fig.savefig('./freq_data.png')
    fig.clf()

    ax = fig.add_subplot(111)
    ax.set_xlabel('Tau [s]')
    ax.set_ylabel('Deviation [Hz]')
    ax.set_yscale('log')

    ax.errorbar(
        taus,
        adevs,
        yerr=conf_int_adev,
        markersize=3,
        fmt='o',
        label='ADEV'
    )
    ax.errorbar(
        taus,
        adevs_overlapped,
        yerr=conf_int_adev_overlapped,
        markersize=3,
        fmt='^',
        label='ADEV overlapped'
    )
    ax.errorbar(
        taus,
        hdevs,
        yerr=conf_int_hdev,
        markersize=3,
        fmt='x',
        label='HDEV'
    )
    ax.legend(loc=0)

    plt.tight_layout()
    fig.savefig('./deviations.png')