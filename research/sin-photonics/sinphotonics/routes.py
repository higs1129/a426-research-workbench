"""Forward retained-mode Gram projection and coherent circular routes."""
import numpy as np
from scipy.interpolate import CubicSpline,PchipInterpolator
from .modes import overlap


def basis(modes,sign=0,reference=None):
    f=np.array([m.field for m in modes]);n=np.array([m.neff for m in modes])
    weights=modes[0].weights
    if any(m.field.shape!=modes[0].field.shape or not np.array_equal(m.weights,weights) for m in modes):
        raise ValueError('Interface modes need a common sampling grid')
    if reference is not None:
        for j,r in enumerate(reference):
            cross=overlap(r.field[None],f[j:j+1],weights)[0,0]
            if abs(cross)<.85:
                raise ValueError('Spectral mode tracking overlap below .85')
            f[j]*=np.exp(-1j*np.angle(cross))
    if sign>0:
        if not np.allclose(modes[0].x,-modes[0].x[::-1],atol=1e-16):
            raise ValueError('Mirrored bend needs symmetric sampling')
        f=f.reshape(len(modes),6,len(modes[0].y),len(modes[0].x))[:,:,:,::-1].reshape(len(modes),6,-1).copy()
        f[:,[0,4,5]]*=-1
    G=overlap(f,f,weights)
    if not np.allclose(G,G.conj().T,atol=1e-10) or np.linalg.eigvalsh(G).min()<=1e-8 or np.linalg.cond(G)>1e8:
        raise ValueError('Singular / indefinite target Gram matrix')
    if np.any(n.imag>0):
        raise ValueError('Positive passive Im(neff), refusing to mask gain')
    return f,n,G


def matrices(mode_sets,references=None):
    bases={key:basis(ms,key[1],None if references is None else references[key]) for key,ms in mode_sets.items()}
    weights=next(iter(mode_sets.values()))[0].weights
    trans={(b,a):np.linalg.solve(bases[b][2],overlap(bases[b][0],bases[a][0],weights)) for a in bases for b in bases}
    return {k:v[1] for k,v in bases.items()},trans,{k:v[2] for k,v in bases.items()}


def propagate(neffs,transitions,grams,segments,wavelength_nm):
    zero=(0.,0);nmode=len(neffs[zero]);amp=np.eye(nmode,dtype=complex);old=zero
    k0=2*np.pi/(wavelength_nm/1000)
    for seg in segments:
        if seg['kind']=='straight':
            new=zero;length=seg['length_um']
        else:
            new=(float(seg['radius_um']),seg['sign'])
            length=seg['radius_um']*np.deg2rad(seg['angle_deg'])
        amp=transitions[new,old]@amp
        # Keep absolute phase; all segment interference remains coherent.
        amp=np.exp(-1j*k0*neffs[new]*length)[:,None]*amp;old=new
    amp=transitions[zero,old]@amp
    G=grams[zero]
    if np.linalg.eigvalsh(G).min()<=0:
        raise ValueError('Interpolated Gram is not positive definite')
    inputs=np.real(np.diag(G))
    powers=np.real(np.einsum('ij,ik,kj->j',amp.conj(),G,amp))/inputs
    return powers,amp


def spectrum(wavelengths,anchors,segments,output_wavelengths):
    """Interpolate phase-aligned matrices, never extrapolate beyond solved anchors."""
    w=np.asarray(wavelengths);target=np.asarray(output_wavelengths)
    if np.any(np.diff(w)<=0) or target.min()<w.min() or target.max()>w.max():
        raise ValueError('Sorted unique anchors and interpolation within their range required')
    keys=list(anchors[0][0]);n=np.array([[a[0][k] for k in keys] for a in anchors])
    if np.any(n.imag>0):
        raise ValueError('Positive imaginary index')
    c=np.array([[[a[1][b,s] for s in keys] for b in keys] for a in anchors])
    g=np.array([[a[2][k] for k in keys] for a in anchors])
    nr=CubicSpline(w,n.real,axis=0);ni=PchipInterpolator(w,np.log(np.maximum(-n.imag,1e-16)),axis=0)
    ci=CubicSpline(w,c,axis=0);gi=CubicSpline(w,g,axis=0)
    outputs=[];amplitudes=[]
    for wl in target:
        nn=nr(wl)-1j*np.exp(ni(wl));cc=ci(wl);gg=gi(wl)
        p,a=propagate(dict(zip(keys,nn)),{(b,s):cc[i,j] for i,b in enumerate(keys) for j,s in enumerate(keys)},dict(zip(keys,gg)),segments,wl)
        outputs.append(p);amplitudes.append(a)
    return np.array(outputs),np.array(amplitudes)
