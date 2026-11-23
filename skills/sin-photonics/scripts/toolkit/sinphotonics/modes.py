"""Explicit NPZ catalog, polarization/node identification, phase and power conventions.

Raw COMSOL cylindrical (Er,Ez,Ephi) orientation differs from the straight
Cartesian (Ex,Ey,Ez) basis. Coupler and interface conventions are explicit;
they reproduce the two frozen derivations, not interchangeable field arrays.
"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from .geometry import CrossSection, cells

C0 = 299792458.


def node_count(raw, component):
    a = raw[2*component] + 1j*raw[2*component+1]
    a = (a*np.exp(-1j*np.angle(a[np.argmax(abs(a))]))).real
    a = a[abs(a) > .02*max(abs(a))]
    return int(np.sum(a[1:]*a[:-1] < 0))


def catalog(folder):
    rows = []
    for path in sorted(Path(folder).glob('*.npz')):
        with np.load(path, allow_pickle=False) as z:
            if 'info' not in z:
                continue
            for j, v in enumerate(z['info'].T):
                if not np.isfinite(v).all():
                    raise ValueError(f'Nonfinite mode metadata in {path}')
                pol = 'TE' if v[3] > .8 else ('TM' if v[3] < .2 else 'hybrid')
                nodes = node_count(z[f'line_{j}'], 0 if pol == 'TE' else 1)
                rows.append(dict(source=str(path.resolve()), solution=j, width_bottom_um=v[6],
                    wavelength_nm=v[7], radius_um=v[8], neff_real=v[0], neff_imag=v[1],
                    core_fraction=v[2], TE_fraction=v[3], n_core=v[4], n_oxide=v[5],
                    mode=pol+str(nodes), nodes=nodes, full_field=f'full_{j}' in z))
    return rows


def select(rows, width, wl, radius, label, full=False):
    candidates = [r for r in rows if abs(r['width_bottom_um']-width) < 1e-7
                  and abs(r['wavelength_nm']-wl) < 1e-5 and abs(r['radius_um']-radius) < 1e-6
                  and r['mode'] == label and r['core_fraction'] > .015
                  and r['neff_real'] > r['n_oxide'] and abs(r['neff_imag']) < .03
                  and (r['full_field'] or not full)]
    if not candidates:
        raise ValueError(f'No retained {label}: width={width}, wavelength={wl}, radius={radius}, full={full}')
    candidates.sort(key=lambda r: r['core_fraction'], reverse=True)
    if len(candidates) > 1 and abs(candidates[0]['neff_real']-candidates[1]['neff_real']) > 1e-5:
        if candidates[1]['core_fraction'] > .8*candidates[0]['core_fraction']:
            raise ValueError('Ambiguous mode branch: refine search/inspect fields')
    return candidates[0]


def dispersion(rows, width, wl, radius, label, step_nm=2):
    br = [select(rows, width, w, radius, label) for w in [wl-step_nm, wl, wl+step_nm]]
    lines = []
    for r in br:
        with np.load(r['source']) as z:
            raw = z[f'line_{r["solution"]}']
        a = raw[::2]+1j*raw[1::2]
        lines.append(a.ravel()/np.linalg.norm(a))
    overlaps = [float(abs(np.vdot(lines[i], lines[i+1]))) for i in range(2)]
    if min(overlaps) < .85 or max(abs(np.diff([r['neff_real'] for r in br]))) > .02:
        raise ValueError(f'Branch tracking failed: line overlaps {overlaps}')
    ng = br[1]['neff_real']-wl*(br[2]['neff_real']-br[0]['neff_real'])/(2*step_nm)
    if ng <= 0:
        raise ValueError('Nonpositive group index')
    im = br[1]['neff_imag']
    if im > 0:
        raise ValueError('Passive convention violated: Im(neff)>0')
    return dict(neff=br[1]['neff_real'], imag_neff=im, ng=ng,
                FSR_GHz=C0/(2*np.pi*radius*1e-6*ng)/1e9 if radius else None,
                ideal_geometry_Q=ng/(-2*im) if im < 0 and radius else None,
                derivative_step_nm=step_nm, line_overlap_min=min(overlaps))


@dataclass
class Mode:
    row: dict
    cs: CrossSection
    field: np.ndarray
    core: np.ndarray
    x: np.ndarray
    y: np.ndarray
    weights: np.ndarray
    eta: np.ndarray
    cy: np.ndarray

    @property
    def neff(self):
        return complex(self.row['neff_real'], self.row['neff_imag'])

    def sampler(self):
        f = self.field[:3].reshape(3,len(self.y),len(self.x)).transpose(1,2,0)
        ip = RegularGridInterpolator((self.y,self.x),f,bounds_error=False,fill_value=0)
        fc = self.core.reshape(3,len(self.cy),len(self.eta)).transpose(1,2,0)
        cp = RegularGridInterpolator((self.cy,self.eta),fc,bounds_error=False,fill_value=None)
        mid = self.row['width_bottom_um']*1e-6-self.cs.h*self.cs.cot
        def sample(u,v,incore=False):
            u,v = np.broadcast_arrays(u,v)
            points = np.column_stack([v.ravel(), (u/(mid/2-v*self.cs.cot) if incore else u).ravel()])
            return (cp if incore else ip)(points).reshape(u.shape+(3,))
        return sample


def load(row, cs, convention='coupler'):
    with np.load(row['source'], allow_pickle=False) as z:
        j = row['solution']
        raw, cr, ln = z[f'full_{j}'], z[f'core_{j}'], z[f'line_{j}']
        x,y,eta,cy = (z[k].ravel() for k in ('x','y','eta','core_y'))
        xe,xs,ye,ys = cs.grid()
        expected_x,wx = cells(xe,xs); expected_y,wy = cells(ye,ys)
        if 'wx' in z:
            # New exports carry the actual cell measure; do not reconstruct a
            # ceil() grid from rounded geometry metadata.
            wx,wy=z['wx'].ravel(),z['wy'].ravel()
            if not np.allclose(z['cross_section'].ravel(),[cs.thickness_nm/1000,cs.wall_deg,cs.lower_oxide_um,cs.upper_oxide_um],rtol=0,atol=1e-12):
                raise ValueError('Exported cross-section metadata mismatch')
            expected_x=xe[0]*1e-6+np.cumsum(wx)-wx/2
            expected_y=ye[0]*1e-6+np.cumsum(wy)-wy/2
            if min(wx.min(),wy.min())<=0 or abs(sum(wx)-(xe[-1]-xe[0])*1e-6)>1e-15 or abs(sum(wy)-(ye[-1]-ye[0])*1e-6)>1e-15:
                raise ValueError('Invalid exported cell measures')
        if x.shape != expected_x.shape or y.shape != expected_y.shape or not np.allclose(x,expected_x,atol=1e-16,rtol=0) or not np.allclose(y,expected_y,atol=1e-16,rtol=0):
            raise ValueError('Solver / postprocessor sampling grid mismatch; check thickness and oxide configuration')
    if not np.isfinite(raw).all() or not np.isfinite(cr).all():
        raise ValueError('Nonfinite field')
    f, fc = raw[::2]+1j*raw[1::2], cr[::2]+1j*cr[1::2]
    weight = np.outer(wy,wx).ravel()
    power = .5*np.real(np.sum((f[0]*f[4].conj()-f[1]*f[3].conj())*weight))
    if power == 0 or row['neff_imag'] > 0:
        raise ValueError('Zero mode power or positive passive Im(neff)')
    if convention == 'coupler' and row['radius_um'] > 0:
        if power >= 0:
            raise ValueError('Unexpected cylindrical orientation in coupler field')
        f[3:] *= -1
    elif power < 0:
        f[[2,3,4]] *= -1; fc[2] *= -1
    pol = 0 if row['mode'].startswith('TE') else 1
    line = ln[2*pol]+1j*ln[2*pol+1]
    gauge = np.exp(-1j*np.angle(line[np.argmax(abs(line))]))
    norm = np.sqrt(power if power>0 else -power)
    f *= gauge/norm; fc *= gauge/norm
    return Mode(row,cs,f,fc,x,y,weight,eta,cy)


def overlap(target, source, weights):
    return .25*((target[:,4].conj()*weights)@source[:,0].T
                -(target[:,3].conj()*weights)@source[:,1].T
                +(target[:,0].conj()*weights)@source[:,4].T
                -(target[:,1].conj()*weights)@source[:,3].T)
