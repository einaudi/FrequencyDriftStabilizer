# -*- coding: utf-8 -*-

cmds = {
    'control': {
        'version': bytes([0x01]),
        'reset': bytes([0x0A]),
        'sync enable': bytes([0x0F])
    },
    'rate': {
        '1ms': bytes([0x20]),
        '2ms': bytes([0x21]),
        '5ms': bytes([0x22]),
        '10ms': bytes([0x23]),
        '20ms': bytes([0x24]),
        '50ms': bytes([0x25]),
        '100ms': bytes([0x26]),
        '200ms': bytes([0x27]),
        '500ms': bytes([0x28]),
        '1s': bytes([0x29]),
        '2s': bytes([0x2A]),
        '5s': bytes([0x2B]),
        '10s': bytes([0x2C]),
        '20s': bytes([0x2D])
    },
    'channel': {
        'all': bytes([0x30]),
        '1': bytes([0x31]),
        '2': bytes([0x32]),
        '3': bytes([0x33]),
        '4': bytes([0x34])
    },
    'mode': {
        'phase': bytes([0x40]),
        'phase avg': bytes([0x41]),
        'frequency': bytes([0x42]),
        'frequency avg': bytes([0x43]),
        'phase diff': bytes([0x44]),
        'phase diff avg': bytes([0x45])
    },
    'scrambler': {
        'off': bytes([0x50]),
        'auto': bytes([0x5E]),
        'trim': bytes([0x5F])
    }
}

cmds_values = {
    'rate': {
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
}