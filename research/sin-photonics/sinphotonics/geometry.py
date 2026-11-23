from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class CrossSection:
    thickness_nm: float = 300
    wall_deg: float = 86
    size_reference: str = 'bottom'
    lower_oxide_um: float = 4
    upper_oxide_um: float = 3
    material: str = 'reference300-v1'

    @property
    def h(self):
        return self.thickness_nm * 1e-9

    @property
    def cot(self):
        return 1 / math.tan(math.radians(self.wall_deg))

    def bottom_width(self, width_um):
        return width_um + {'bottom': 0, 'mid': 1, 'top': 2}[self.size_reference]*self.h*1e6*self.cot

    def bottom_gap(self, gap_um):
        # Both sidewalls retreat inward from their bottom edges.
        return gap_um - {'bottom': 0, 'mid': 1, 'top': 2}[self.size_reference]*self.h*1e6*self.cot

    def grid(self):
        h = self.thickness_nm/1000
        return ([-7.8,-3,-1,1,3,7.8], [.1,.035,.02,.035,.1],
                [-5.5,-self.lower_oxide_um-h/2,-1-h/2,-h/2,h/2,1+h/2,self.upper_oxide_um+h/2,4.5],
                [.10,.08,.03,.01,.03,.08,.10])


def cells(edges, steps):
    centers, weights = [], []
    for lo, hi, step in zip(edges[:-1], edges[1:], steps):
        if hi <= lo:
            raise ValueError('Invalid integration-domain ordering')
        n = int(np.ceil((hi-lo)/step))
        centers.extend(lo+(np.arange(n)+.5)*(hi-lo)/n)
        weights.extend([(hi-lo)/n]*n)
    return np.array(centers)*1e-6, np.array(weights)*1e-6


def rounded_route(vertices, radius_um):
    """Orthogonal polyline with exact circular corner lengths, no Euler claim."""
    vertices = np.asarray(vertices, float)
    previous = vertices[0]
    segments = []
    for i, v in enumerate(vertices[1:-1], 1):
        a, b = v-vertices[i-1], vertices[i+1]-v
        a /= np.linalg.norm(a); b /= np.linalg.norm(b)
        if abs(a@b) > 1e-9:
            raise ValueError('Rounded polyline requires 90 degree corners')
        p, q = v-a*radius_um, v+b*radius_um
        length = float((p-previous)@a)
        if length < 0:
            raise ValueError('Corners overlap; shorten radius or extend straight')
        segments += [dict(kind='straight', length_um=length),
                     dict(kind='arc', radius_um=radius_um, angle_deg=90,
                          sign=int(a[0]*b[1]-a[1]*b[0]))]
        previous = q
    tail = vertices[-1]-previous
    if tail@b < 0:
        raise ValueError('Final arc extends beyond endpoint')
    segments.append(dict(kind='straight', length_um=float(np.linalg.norm(tail))))
    return segments
