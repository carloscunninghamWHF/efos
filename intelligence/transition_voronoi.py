"""Clipped Voronoi polygons on the 120 x 80 StatsBomb pitch.

Used only to visualize interpolated snapshots from StatsBomb 360. It is NOT an
estimate of tracking or true occupied space outside the visible camera view.
"""
from __future__ import annotations
import numpy as np


def _clip(poly: np.ndarray, normal: np.ndarray, boundary: float) -> np.ndarray:
    """Keep x satisfying normal·x <= boundary (half-plane / perpendicular bisector)."""
    if len(poly) == 0: return poly
    result=[]
    for a,b in zip(poly, np.roll(poly,-1,axis=0)):
        aa=float(np.dot(normal,a)-boundary)
        bb=float(np.dot(normal,b)-boundary)
        inside_a=aa<=1e-9
        inside_b=bb<=1e-9
        if inside_a: result.append(a)
        if inside_a!=inside_b:
            t=aa/(aa-bb)
            result.append(a+t*(b-a))
    return np.asarray(result,dtype=float).reshape(-1,2)


def voronoi_polygons(pts: np.ndarray) -> list[np.ndarray]:
    """Return each player's closest-point polygon within the field, in input order."""
    points=np.asarray(pts,dtype=float).reshape(-1,2)
    bounds=np.asarray([[0,0],[120,0],[120,80],[0,80]],dtype=float)
    out=[]
    for i,a in enumerate(points):
        poly=bounds.copy()
        for j,b in enumerate(points):
            if i==j:continue
            d=b-a
            if float(np.dot(d,d))<1e-8: continue
            # ||x-a||² <= ||x-b||² -> 2(b-a)·x <= ||b||²-||a||²
            poly=_clip(poly,d,(float(np.dot(b,b))-float(np.dot(a,a)))/2)
            if not len(poly):break
        out.append(poly)
    return out
