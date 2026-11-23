"""One material source for both Python and the native solver."""
import json
from pathlib import Path
import numpy as np

DATA = json.loads(Path(__file__).with_name('materials.json').read_text(encoding='utf-8'))


def indices(wavelength_nm, preset='reference300-v1'):
    if preset != 'reference300-v1':
        raise ValueError(f'Unknown material: {preset}')
    w = np.asarray(wavelength_nm, dtype=float) / 1000
    if np.any((w < 1.53) | (w > 1.57)):
        raise ValueError('Material workflow qualified only over 1530–1570 nm')
    def sell(kind):
        return np.sqrt(1 + sum(b*w*w/(w*w-c) for b, c in zip(DATA[kind+'_B'], DATA[kind+'_C'])))
    core = sell('sin')
    return core, sell('oxide')


def expression(kind, preset='reference300-v1'):
    s = 'sqrt(1'+''.join(f'+({b})*(lambda0/1[um])^2/((lambda0/1[um])^2-({c}))'
                       for b, c in zip(DATA[kind+'_B'], DATA[kind+'_C']))+')'
    return s
