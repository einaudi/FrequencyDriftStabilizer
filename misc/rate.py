# -*- coding: utf-8 -*-

import os
import yaml

rate_values_kk = {
    '1ms': 1e-3,
    '2ms': 2e-3,
    '5ms': 5e-3,
    '10ms': 1e-2,
    '20ms': 2e-2,
    '50ms': 5e-2,
    '100ms': 1e-1,
    '200ms': 2e-1,
    '500ms': 5e-1,
    '1s': 1,
    '2s': 2,
    '5s': 5,
    '10s': 10,
    '20s': 20
}

rate_values_ADS1256 = {
    '33us': 33e-6,
    '66us': 66e-6,
    '133us': 133e-6,
    '266us': 266e-6,
    '500us': 500e-6,
    '1ms': 1e-3,
    '2ms': 2e-3,
    '10ms': 10e-3,
    '16ms': 16e-3,
    '20ms': 20e-3,
    '33ms': 33e-3,
    '40ms': 40e-3,
    '66ms': 66e-3,
    '100ms': 100e-3,
    '200ms': 200e-3,
    '400ms': 400e-3
}


config_path = os.path.join("./", "config", "devices.yml")
with open(config_path) as config_file:
    devices_config = yaml.safe_load(config_file)

if devices_config['ADC'] == 'Dummy':
    rate_values = rate_values_ADS1256
elif devices_config['ADC'] == 'FXE':
    rate_values = rate_values_kk
elif devices_config['ADC'] == 'Keysight':
    rate_values = rate_values_kk
elif devices_config['ADC'] == 'ADS1256':
    rate_values = rate_values_ADS1256
else:
    rate_values = []