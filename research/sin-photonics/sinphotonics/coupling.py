"""Ring–straight-bus spatial overlap and complex Hermitian star evolution."""
import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.integrate import cumulative_trapezoid
from .modes import C0

EPS0 = 8.8541878128e-12


def quad(width_um, cs, nu, nv):
    a,wa = leggauss(nu); b,wb = leggauss(nv)
    y = b*cs.h/2
    half = width_um*1e-6/2-(y+cs.h/2)*cs.cot
    u = half[:,None]*a; v = np.broadcast_to(y[:,None],u.shape)
    weights = wb[:,None]*wa*half[:,None]*cs.h/2
    return u.ravel(),v.ravel(),weights.ravel()


def kernels(ring,bus,gap_um,step_um=.06,nu=48,nv=24,extent_um=30,diagonal_phase=False):
    rad = ring.row['radius_um']*1e-6; wl = ring.row['wavelength_nm']*1e-9
    rb = rad+(ring.row['width_bottom_um']+bus.row['width_bottom_um'])*.5e-6+gap_um*1e-6
    s = np.linspace(-extent_um,extent_um,int(np.ceil(2*extent_um/step_um))+1)*1e-6
    ur,vr,wr = quad(ring.row['width_bottom_um'],ring.cs,nu,nv)
    ub,vb,wb = quad(bus.row['width_bottom_um'],bus.cs,nu,nv)
    rs,bs = ring.sampler(),bus.sampler()
    er,eb = rs(ur,vr,True),bs(ub,vb,True)
    k0 = 2*np.pi/wl; q = k0*ring.neff.real*rad; beta = k0*bus.neff.real
    pref = C0*k0*EPS0*(ring.row['n_core']**2-ring.row['n_oxide']**2)/4
    pr,pb = np.zeros(len(s)),np.zeros(len(s))
    if diagonal_phase:
        if extent_um*1e-6 >= rad+min(ur):
            raise ValueError('Self-phase integration window exceeds local ring chart')
        dr,db = [],[]
        for t in s:
            co = np.cos(t/rad); rho = (rb+ub)/co
            dr.append(pref*np.sum(np.sum(abs(rs(rho-rad,vb))**2,axis=-1)*wb/co*rho/rad))
            rho = rad+ur; x = np.sqrt(rho*rho-t*t)
            db.append(pref*np.sum(np.sum(abs(bs(x-rb,vr))**2,axis=-1)*wr*rho/x))
        pr = cumulative_trapezoid(dr,s,initial=0); pb = cumulative_trapezoid(db,s,initial=0)
    gb,gr = np.zeros(len(s),complex),np.zeros(len(s),complex)
    for i,t in enumerate(s):
        xx = rb+ub; rho = np.hypot(xx,t); phi = np.arctan2(t,xx)
        f = rs(rho-rad,vb); co,si = np.cos(phi),np.sin(phi)
        rot = np.stack([f[:,0]*co-f[:,2]*si,f[:,1],f[:,0]*si+f[:,2]*co],axis=1)
        phase = beta*t-q*phi+pb[i]-np.interp(rad*phi,s,pr)
        gb[i] = pref*np.sum(np.sum(eb.conj()*rot,axis=1)*np.exp(1j*phase)*wb)
        phi=t/rad; rho=rad+ur; xx=rho*np.cos(phi); zz=rho*np.sin(phi)
        f=bs(xx-rb,vr); co,si=np.cos(phi),np.sin(phi)
        rot=np.stack([er[:,0]*co-er[:,2]*si,er[:,1],er[:,0]*si+er[:,2]*co],axis=1)
        phase=beta*zz-q*phi+np.interp(zz,s,pb)-pr[i]
        gr[i]=pref*np.sum(np.sum(f.conj()*rot,axis=1)*np.exp(1j*phase)*wr*rho/rad)
    return s,gb,gr


def evolve(s,g):
    state=np.zeros(len(g)+1,complex);state[0]=1
    def rhs(a,v):
        return -1j*np.r_[np.vdot(v,a[1:]),v*a[0]]
    for i,ds in enumerate(np.diff(s)):
        a,b=g[:,i],g[:,i+1];mid=(a+b)/2
        k1=rhs(state,a);k2=rhs(state+ds*k1/2,mid)
        k3=rhs(state+ds*k2/2,mid);k4=rhs(state+ds*k3,b)
        state+=ds*(k1+2*k2+2*k3+k4)/6
    return state


def quality_factors(powers,ng,radius_um,wavelength_nm):
    total=float(sum(powers))
    if not 0<=total<1 or np.any(np.asarray(powers)<0):
        raise ValueError('Qc requires 0 <= retained K_total < 1')
    if total==0:
        return np.inf,np.full(len(powers),np.inf)
    qt=(2*np.pi/(wavelength_nm*1e-9))*ng*2*np.pi*radius_um*1e-6/(-np.log1p(-total))
    return qt,np.divide(qt*total,powers,out=np.full(len(powers),np.inf),where=np.asarray(powers)>0)


def calculate(ring,buses,gap_um,ng,**integration):
    kk=[kernels(ring,b,gap_um,**integration) for b in buses]
    s=kk[0][0];g=np.array([k[1] for k in kk]);alt=np.array([k[2] for k in kk])
    state=evolve(s,g);powers=abs(state[1:])**2;kt=float(sum(powers))
    amps=np.trapezoid(g,s,axis=1);alts=np.trapezoid(alt,s,axis=1)
    errors=abs(amps-alts)/np.maximum(abs(amps),1e-30)
    balance=float(sum(abs(state)**2)); reasons=[]
    if kt>.01: reasons.append('retained_exchange_above_1_percent')
    if max(errors)>.02: reasons.append('integration_domain_amplitude_discrepancy_above_2_percent')
    if abs(balance-1)>1e-5: reasons.append('retained_evolution_balance_error')
    if any(b.row['mode'].startswith('TM') for b in buses):
        reasons.append('leaky_TM_coupling_not_physically_validated')
    qt,qj=quality_factors(powers,ng,ring.row['radius_um'],ring.row['wavelength_nm'])
    result=dict(gap_bottom_um=gap_um,K_total=kt,Qc_total=qt,power_balance=balance,
                qualified=not reasons,status='diagnostic_only' if reasons else 'screened_approximation',reasons=reasons)
    for j,b in enumerate(buses):
        label=b.row['mode'];result.update({f'Qc_{label}':qj[j],f'K_{label}':powers[j],
            f'overlap_discrepancy_{label}':errors[j],f'amplitude_real_{label}':state[j+1].real,
            f'amplitude_imag_{label}':state[j+1].imag})
    return result,dict(s_m=s,kernel_per_m=g,alternate_kernel_per_m=alt,output_amplitude=state)
