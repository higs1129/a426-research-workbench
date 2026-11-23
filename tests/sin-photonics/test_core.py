"""Synthetic invariants; real datasets remain in ignored local resources."""
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'research/sin-photonics'))
from sinphotonics.geometry import CrossSection,cells,rounded_route
from sinphotonics.materials import indices
from sinphotonics.coupling import evolve,quality_factors,quad
from sinphotonics.routes import propagate


class PhysicsInvariants(unittest.TestCase):
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
