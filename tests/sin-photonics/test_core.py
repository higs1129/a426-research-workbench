"""Synthetic invariants; real datasets remain in ignored local resources."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'research/sin-photonics'))
from sinphotonics.geometry import CrossSection,cells,rounded_route
from sinphotonics.materials import indices
from sinphotonics.coupling import evolve,quality_factors,quad,window_plan,converged_window,mixed_error
from sinphotonics.scan import plan
from sinphotonics.routes import propagate


class PhysicsInvariants(unittest.TestCase):
    def test_prefixed_svg_is_rejected_in_html(self):
        from sinphotonics.report import check_html
        text='<html><ns0:svg xmlns:ns0="http://www.w3.org/2000/svg"><ns0:text>x</ns0:text></ns0:svg></html>'
        with patch.object(Path,'read_text',return_value=text):
            with self.assertRaisesRegex(ValueError,'Prefixed SVG'):
                check_html('unused-in-memory.html')
    def test_small_radius_window_reachability(self):
        for radius in [30.001,35,40,57.932443]:
            cfg,sequence,detail=window_plan(radius,{}, {})
            self.assertGreaterEqual(len(sequence)-1,cfg['consecutive_passes'])
            self.assertLess(max(sequence),.8*radius)
            self.assertEqual(detail['initial_mode'],'automatic')
        with self.assertRaisesRegex(ValueError,'only 1 expansion'):
            window_plan(40,{'extent_um':30},{})
        with self.assertRaisesRegex(ValueError,'below limit'):
            window_plan(35,{'extent_um':30},{})

    def test_zero_fill_support_cannot_pass_stable_window(self):
        from types import SimpleNamespace
        def stable(*args,**kwargs):
            return dict(amps=np.array([1e-10j]),alts=np.array([1e-10j]),state=np.array([1,1e-10j]),
                powers=np.array([1e-20]),tails=np.zeros((2,1)),envelopes=np.ones((2,1)),
                support=[dict(ring=dict(outside=10,boundary_field_ratio=.01))])
        with patch('sinphotonics.coupling.evaluate_window',side_effect=stable):
            _,diagnostic=converged_window(SimpleNamespace(row={'radius_um':40}),[],1,{}, {})
        self.assertEqual(diagnostic['status'],'sampling_domain_truncated')
        self.assertFalse(diagnostic['converged'])
        self.assertEqual(len(diagnostic['comparisons']),2)
        def decayed(*args,**kwargs):
            value=stable();value['support'][0]['ring']['boundary_field_ratio']=1e-6
            return value
        with patch('sinphotonics.coupling.evaluate_window',side_effect=decayed):
            for radius in [30.001,35,40]:
                _,diagnostic=converged_window(SimpleNamespace(row={'radius_um':radius}),[],1,{}, {})
                self.assertTrue(diagnostic['converged'])
                self.assertEqual(len(diagnostic['comparisons']),2)

    def test_mixed_tolerances_near_cancellation(self):
        self.assertTrue(mixed_error(np.array([1e-12j]),np.array([-1e-12j]),5e-4,1e-7)[2])
        self.assertFalse(mixed_error(np.array([2e-7j]),np.array([-2e-7j]),5e-4,1e-7)[2])

    def test_spectral_anchor_and_mode_deduplication(self):
        cfg=dict(scan=dict(ring_widths_um=[1.2,1.3],bus_widths_um=[1.1,1.2],ring_radii_um=[40,60],wavelengths_nm=[1550,1552]),gaps_um=[1,1.2])
        result=plan(cfg,CrossSection())
        self.assertEqual(result['ring']['wavelengths'],[1548,1550,1552,1554])
        self.assertEqual(result['native_mode_cases'],24)
        self.assertEqual(result['coupling_cases'],32)

    def test_material_dispersion(self):
        nc,no=indices(1550)
        self.assertAlmostEqual(float(nc),1.996351530914008,13)
        self.assertAlmostEqual(float(no),1.444266379413012,13)
        self.assertNotEqual(float(indices(1540)[0]),float(indices(1560)[0]))
        with self.assertRaises(ValueError):indices(1550,'unknown')

    def test_cross_section_measure_changes_with_thickness(self):
        for h in [280,300,310]:
            cs=CrossSection(thickness_nm=h,wall_deg=87,size_reference='mid')
            bottom=cs.bottom_width(1.2)
            x,y,w=quad(bottom,cs,32,16)
            area=(bottom*1e-6-cs.h*cs.cot)*cs.h
            self.assertAlmostEqual(w.sum()/area,1,13)
            self.assertAlmostEqual(cs.bottom_gap(1.2),1.2-cs.h*1e6*cs.cot)
            xe,xs,ye,ys=cs.grid();_,wy=cells(ye,ys)
            self.assertAlmostEqual(wy.sum(),10e-6,15)

    def test_exact_uniform_two_mode_solution(self):
        s=np.linspace(0,1,1001);g=np.full((1,len(s)),.3+.4j)
        a=evolve(s,g)
        np.testing.assert_allclose(a,[np.cos(.5),-1j*(.3+.4j)/.5*np.sin(.5)],atol=1e-13)
        self.assertAlmostEqual(sum(abs(a)**2),1,13)

    def test_zero_coupling_and_channel_q_definition(self):
        qt,qj=quality_factors([0,0],1.96,58,1550)
        self.assertTrue(np.isinf(qt));self.assertTrue(np.isinf(qj).all())
        qt,qj=quality_factors([.001,.003],1.96,58,1550)
        self.assertAlmostEqual(sum(1/qj),1/qt,16)
        with self.assertRaises(ValueError):quality_factors([1],1.96,58,1550)

    def test_passive_complex_propagation_and_gram_power(self):
        key=(0.,0);n=np.array([1.6-1e-4j]);G=np.eye(1);length=10
        p,a=propagate({key:n},{(key,key):G},{key:G},[dict(kind='straight',length_um=length)],1550)
        self.assertAlmostEqual(p[0],np.exp(-2*(2*np.pi/1.55)*1e-4*length),14)

    def test_reject_overlapping_corners(self):
        with self.assertRaises(ValueError):rounded_route([(0,0),(1,0),(1,1)],2)


if __name__=='__main__':unittest.main()
