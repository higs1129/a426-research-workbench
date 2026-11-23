# Physical conventions and interpretation

Fields use exp(+iωt−iβs). Passive modes must have Im(neff) ≤ 0; propagation is exp[−i(2π/λ)neff L]. Positive imaginary index is rejected, never made passive with abs(). Cylindrical COMSOL fields require explicit orientation transforms; the coupler and route-interface transforms follow their frozen source derivations and are not interchangeable arrays.

TE is dominated by horizontal/radial electric field; TM by vertical electric field. The selector uses >0.8 / <0.2 core polarization, core energy fraction >0.015, transverse node count and the oxide light line. Degenerate/ambiguous selections fail. Group index is neff−λ dneff/dλ from the bracketing central difference; adjacent line-field overlap guards branch continuity. These are identification diagnostics, not proof of every branch over arbitrary geometries.

Power normalization uses the signed vector Poynting integral on the declared finite sampling window. Complex gauge is fixed by a dominant component; spectral route fields are additionally aligned by power overlap. Full arrays are interpolation samples, not native FEM nodes. New NPZ exports store cell weights and cross-section metadata. Legacy grids are accepted only under their matching 300 nm configuration.

For route interfaces, G is the target-basis Hermitian power Gram matrix, C is cross-overlap, and amplitudes map by G⁻¹C. Reject ill-conditioned or indefinite G. Output power is a†Ga, normalized by input-basis power. |a_j|² is a coefficient contribution; in a nonorthogonal basis these contributions need not add to total power. Unretained forward power is not fully computed radiation. Reflections, radiation continuum and recapture are absent.

Ring-bus propagation retains a ring input and the requested independent bus channels in a Hermitian star system. It preserves complex amplitudes and checks bus Gram deviation; it does not implement a general nonorthogonal coupled-mode metric. The two dielectric integration domains need not agree exactly for nonorthogonal isolated modes. Their difference is a numerical/model diagnostic. Fixed-field `diagonal_phase` adds self-phase perturbations only.

With Kj the output power in retained bus channel j, Ktot=ΣKj, Trt=2πRng/c and ω=2πc/λ:

- Qc,total = ωTrt / [−ln(1−Ktot)]
- Qc,j = Qc,total Ktot/Kj
- Ktot=0 gives infinite Q; a zero channel gives infinite channel Q. JSON represents infinity as null; the explanation remains in the result.

These require 0≤Ktot<1 and a meaningful weak-coupling, retained-channel approximation. Qc,total is not loaded Q. The default screening limits Ktot≤0.01, integration-domain amplitude discrepancy≤0.02, evolution balance error≤1e−5 are empirical diagnostics, not physical error bounds.

The reference TM ring has ideal geometric leakage Q≈2.9×10⁴. The archived 33 gap points failed their previous diagnostics; finer quadrature did not cure domain discrepancy. Keep both raw numbers and reasons visibly diagnostic. A lossy/nonorthogonal coupling theory or joint local full-wave calculation is a future capability, not something achieved by repeated integration refinement.

Broadband routes interpolate phase-aligned real indices, interface matrices and Gram matrices with cubic splines; negative imaginary index magnitude uses log-PCHIP with a declared 10⁻¹⁶ numerical floor. Extrapolation is rejected. A separate 1555 nm solved anchor tests the reference interpolation. Every requested wavelength is propagated coherently. Spectral peak-to-peak includes the smooth material trend and is not a detrended ripple metric.

Experimental interpretation preserves source fit branches and inclusion flags. Compare real μ=0 wavelengths against the explicitly stated 1550 nm design baseline. Q0 can contain unobserved-channel loss, 86° is a design assumption, and ng derived from FSR is not independent evidence. End-to-end insertion loss cannot isolate bend loss.
