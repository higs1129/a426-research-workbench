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


def boundary_ratio(mode):
    """Inspect nonzero edge samples before the interpolator's zero fill.

    Only core-height slices are queried by the coupling integrals. Three edge
    columns avoid mistaking an accidentally small single boundary sample for
    field decay. This is a finite-window diagnostic, not a radiation bound.
    """
    f=mode.field[:3].reshape(3,len(mode.y),len(mode.x))
    strip=np.sqrt(np.sum(abs(f[:,abs(mode.y)<=mode.cs.h/2,:])**2,axis=0))
    return float(max(strip[:,:3].max(),strip[:,-3:].max())/max(strip.max(),1e-300))


def kernels(ring,bus,gap_um,step_um=.06,nu=48,nv=24,extent_um=30,diagonal_phase=False,diagnostics=False):
    rad = ring.row['radius_um']*1e-6; wl = ring.row['wavelength_nm']*1e-9
    if extent_um<=0 or extent_um>=.8*rad*1e6+1e-9:
        raise ValueError('Integration half-window must be positive and below 0.8 R (local forward chart)')
    rb = rad+(ring.row['width_bottom_um']+bus.row['width_bottom_um'])*.5e-6+gap_um*1e-6
    s = np.linspace(-extent_um,extent_um,int(np.ceil(2*extent_um/step_um))+1)*1e-6
    ur,vr,wr = quad(ring.row['width_bottom_um'],ring.cs,nu,nv)
    ub,vb,wb = quad(bus.row['width_bottom_um'],bus.cs,nu,nv)
    support={}
    def audited(mode,name):
        sampler=mode.sampler()
        item=dict(queries=0,outside=0,boundary_field_ratio=boundary_ratio(mode),
                  x_support_um=[float(mode.x[0]*1e6),float(mode.x[-1]*1e6)])
        support[name]=item
        def sample(u,v,incore=False):
            if not incore:
                u,v=np.broadcast_arrays(u,v)
                item['queries']+=u.size
                item['outside']+=int(np.count_nonzero((u<mode.x[0])|(u>mode.x[-1])|(v<mode.y[0])|(v>mode.y[-1])))
            return sampler(u,v,incore)
        return sample
    rs,bs = audited(ring,'ring'),audited(bus,'bus')
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
        # Use the same center-referenced interaction gauge at every window.
        pr-=np.interp(0,s,pr);pb-=np.interp(0,s,pb)
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
    return (s,gb,gr,support) if diagnostics else (s,gb,gr)


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


def evaluate_window(ring,buses,gap_um,**integration):
    kk=[kernels(ring,b,gap_um,diagnostics=True,**integration) for b in buses]
    s=kk[0][0];g=np.array([k[1] for k in kk]);alt=np.array([k[2] for k in kk])
    state=evolve(s,g);powers=abs(state[1:])**2;kt=float(sum(powers))
    amps=np.trapezoid(g,s,axis=1);alts=np.trapezoid(alt,s,axis=1)
    # Absolute envelope in the outer 20%, independent of coherent cancellation.
    tail=abs(s)>=.8*max(abs(s))
    envelopes=np.array([np.trapezoid(abs(k),s,axis=1) for k in [g,alt]])
    tails=np.array([np.trapezoid(np.where(tail,abs(k),0),s,axis=1) for k in [g,alt]])
    return dict(s=s,g=g,alt=alt,state=state,powers=powers,kt=kt,amps=amps,alts=alts,
                tails=tails,envelopes=envelopes,support=[k[3] for k in kk])


def mixed_error(new,old,relative,absolute):
    delta=abs(np.asarray(new)-np.asarray(old))
    scale=np.maximum(abs(new),abs(old))
    allowed=absolute+relative*scale
    return delta,allowed,bool(np.all(delta<=allowed))


def window_plan(radius_um,integration,control):
    """Reserve enough genuine expansions before the local-coordinate limit."""
    defaults=dict(max_extent_um=60.,growth=1.35,relative_tolerance=5e-4,
        amplitude_absolute_tolerance=1e-7,power_absolute_tolerance=1e-10,
        tail_relative_tolerance=1e-3,boundary_field_tolerance=1e-4,
        consecutive_passes=2,max_comparisons=8)
    cfg={**defaults,**control}
    required=int(cfg['consecutive_passes']);growth=float(cfg['growth'])
    if growth<=1 or required<2 or int(cfg['max_comparisons'])<required:
        raise ValueError('Window needs growth > 1 and max_comparisons >= consecutive_passes >= 2')
    cap=min(float(cfg['max_extent_um']),.8*radius_um*(1-1e-9))
    # Keep the established 30 µm starting window when a capped final step
    # still permits the required comparisons; shrink only when necessary.
    recommended=30. if 30.<cap/growth**(required-1)*(1-1e-10) else cap/growth**required
    explicit='extent_um' in integration
    initial=float(integration.get('extent_um',recommended))
    if initial<=0 or initial>=cap:
        raise ValueError(f'Explicit initial half-window {initial:g} must be positive and below limit {cap:g} µm; omit extent_um for automatic planning (start {recommended:g} µm)')
    sequence=[initial]
    for _ in range(int(cfg['max_comparisons'])):
        nxt=min(cap,sequence[-1]*growth)
        if nxt<=sequence[-1]*(1+1e-10):break
        sequence.append(nxt)
    if len(sequence)-1<required:
        raise ValueError(f'Initial half-window {initial:g} leaves only {len(sequence)-1} expansion(s) below {cap:g} µm, but {required} consecutive comparisons are required; omit extent_um or start at/below {recommended:g} µm')
    return cfg,sequence,dict(initial_mode='explicit' if explicit else 'automatic',
        requested_extent_um=initial if explicit else None,initial_extent_um=initial,
        effective_limit_um=cap,planned_extents_um=sequence)


def converged_window(ring,buses,gap_um,integration,control):
    integration=dict(integration)
    cfg,sequence,plan=window_plan(ring.row['radius_um'],integration,control)
    integration.pop('extent_um',None)
    initial=sequence[0]
    current=evaluate_window(ring,buses,gap_um,extent_um=initial,**integration)
    history=[];extent=initial;consecutive=0;passed=False
    for nxt in sequence[1:]:
        newer=evaluate_window(ring,buses,gap_um,extent_um=nxt,**integration)
        # Both perturbative domains plus the finite-evolution amplitudes.
        olda=np.array([current['amps'],current['alts'],current['state'][1:]])
        newa=np.array([newer['amps'],newer['alts'],newer['state'][1:]])
        da,at,amplitude_ok=mixed_error(newa,olda,cfg['relative_tolerance'],cfg['amplitude_absolute_tolerance'])
        dp,pt,power_ok=mixed_error(newer['powers'],current['powers'],2*cfg['relative_tolerance'],cfg['power_absolute_tolerance'])
        tail_limit=cfg['amplitude_absolute_tolerance']+cfg['tail_relative_tolerance']*newer['envelopes']
        tail_ok=bool(np.all(newer['tails']<=tail_limit))
        support_ok=all(v['outside']==0 or v['boundary_field_ratio']<=cfg['boundary_field_tolerance'] for d in newer['support'] for v in d.values())
        numerical_ok=amplitude_ok and power_ok and tail_ok
        consecutive=consecutive+1 if numerical_ok else 0
        history.append(dict(from_extent_um=extent,to_extent_um=nxt,
            amplitude_delta=da.tolist(),amplitude_allowed=at.tolist(),power_delta=dp.tolist(),power_allowed=pt.tolist(),
            tail_absolute_integral=newer['tails'].tolist(),tail_allowed=tail_limit.tolist(),
            amplitude_ok=amplitude_ok,power_ok=power_ok,tail_ok=tail_ok,sampling_support_ok=support_ok))
        current=newer;extent=nxt
        if consecutive>=cfg['consecutive_passes']:
            passed=support_ok;break
    support_ok=all(v['outside']==0 or v['boundary_field_ratio']<=cfg['boundary_field_tolerance'] for d in current['support'] for v in d.values())
    status='converged' if passed else ('sampling_domain_truncated' if not support_ok else 'unconverged_at_limit')
    return current,dict(status=status,converged=passed,**plan,used_extent_um=extent,
        control=cfg,comparisons=history,sampling_support=current['support'],
        metric_order=['bus_domain_weak_amplitude','ring_domain_weak_amplitude','finite_output_amplitude'],
        note='Mixed absolute/relative amplitude and power tests; absolute envelope tail test. Boundary ratio is a diagnostic, not a rigorous missing-field bound.')


def calculate(ring,buses,gap_um,ng,**integration):
    control=integration.pop('window',{})
    current,window=converged_window(ring,buses,gap_um,integration,control)
    s,g,alt,state,powers,kt,amps,alts=(current[k] for k in ['s','g','alt','state','powers','kt','amps','alts'])
    errors=abs(amps-alts)/np.maximum(abs(amps),1e-30)
    balance=float(sum(abs(state)**2)); reasons=[]
    if not window['converged']:reasons.append('integration_window_'+window['status'])
    if kt>.01: reasons.append('retained_exchange_above_1_percent')
    if np.any(abs(amps-alts)>window['control']['amplitude_absolute_tolerance']+.02*np.maximum(abs(amps),abs(alts))):
        reasons.append('integration_domain_amplitude_discrepancy_above_2_percent')
    if abs(balance-1)>1e-5: reasons.append('retained_evolution_balance_error')
    if any(b.row['mode'].startswith('TM') for b in buses):
        reasons.append('leaky_TM_coupling_not_physically_validated')
    qt,qj=quality_factors(powers,ng,ring.row['radius_um'],ring.row['wavelength_nm'])
    result=dict(gap_bottom_um=gap_um,K_total=kt,Qc_total=qt,power_balance=balance,
                qualified=not reasons,status='diagnostic_only' if reasons else 'screened_approximation',reasons=reasons,
                window_status=window['status'],window_extent_um=window['used_extent_um'],window=window)
    for j,b in enumerate(buses):
        label=b.row['mode'];result.update({f'Qc_{label}':qj[j],f'K_{label}':powers[j],
            f'overlap_discrepancy_{label}':errors[j],f'amplitude_real_{label}':state[j+1].real,
            f'amplitude_imag_{label}':state[j+1].imag})
        result[f'absolute_floor_dominated_{label}']=bool(abs(state[j+1])<=window['control']['amplitude_absolute_tolerance']/window['control']['relative_tolerance'])
        if 0<abs(state[j+1])<=window['control']['amplitude_absolute_tolerance']:
            result['qualified']=False;result['status']='diagnostic_only';reasons.append('channel_Q_relative_accuracy_unresolved_'+label)
    return result,dict(s_m=s,kernel_per_m=g,alternate_kernel_per_m=alt,output_amplitude=state)
