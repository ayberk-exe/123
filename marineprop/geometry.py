"""Parametric, cylindrical-section propeller geometry; SI units, shaft axis +Z.

This is a geometric loft, NOT a hydrodynamic series or a manufacturing certificate.
Right-handed surfaces have dz/dtheta > 0 for the developed chord camber line.
Profiles are symmetric closed-TE NACA 00xx or elliptical sections, without camber.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import io
import json
from math import atan2, cos, isfinite, pi, sin
from pathlib import Path

import numpy as np
import trimesh


@dataclass(frozen=True)
class RadialStation:
    radius_fraction: float  # r/R
    chord_ratio: float      # c/D, developed cylindrical chord
    thickness_ratio: float # t/c
    pitch_factor: float = 1.0  # local P/D = global P/D * factor
    profile: str = 'naca00'


@dataclass(frozen=True)
class PropellerDesign:
    diameter_m: float = 0.08
    blade_count: int = 3
    hub_diameter_m: float = 0.018
    hub_length_m: float = 0.024
    pitch_ratio: float = 0.8
    rake_m: float = 0.0      # root-to-tip axial displacement
    skew_deg: float = 15.0  # root-to-tip cylindrical angular displacement
    handedness: str = 'right'
    stations: tuple[RadialStation, ...] = ()
    section_points: int = 32 # points on each foil side, cosine spaced
    radial_subdivisions: int = 3

    def __post_init__(self):
        for name in ('diameter_m', 'hub_diameter_m', 'hub_length_m', 'pitch_ratio', 'rake_m', 'skew_deg'):
            if not isfinite(getattr(self, name)):
                raise ValueError(f'{name}: finite value required')
        if self.diameter_m <= 0 or not 0 < self.hub_diameter_m < self.diameter_m:
            raise ValueError('0 < hub diameter < propeller diameter required')
        if self.hub_length_m <= 0 or self.pitch_ratio <= 0:
            raise ValueError('Hub length and P/D must be positive')
        if type(self.blade_count) is not int or not 2 <= self.blade_count <= 12:
            raise ValueError('Blade count must be an integer in [2, 12]')
        if type(self.section_points) is not int or not 12 <= self.section_points <= 128:
            raise ValueError('Section points must be an integer in [12, 128]')
        if type(self.radial_subdivisions) is not int or not 1 <= self.radial_subdivisions <= 12:
            raise ValueError('Radial subdivisions must be an integer in [1, 12]')
        if self.handedness not in ('right', 'left'):
            raise ValueError('Handedness must be right or left')
        if abs(self.skew_deg) >= 90 or abs(self.rake_m) >= self.diameter_m:
            raise ValueError('Prototype limits: |skew| < 90 degrees and |rake| < D')
        if not self.stations:
            h = self.hub_diameter_m / self.diameter_m
            r = np.linspace(.9*h, 1, 7)
            stations = tuple(RadialStation(float(x), c, t) for x,c,t in zip(
                r, [.18,.24,.26,.25,.21,.14,.04], [.18,.16,.14,.12,.10,.07,.04]))
            object.__setattr__(self, 'stations', stations)
        if not 3 <= len(self.stations) <= 32:
            raise ValueError('Provide 3–32 radial stations')
        for station in self.stations:
            if not isinstance(station, RadialStation):
                raise ValueError('Station must be a RadialStation')
            if not all(isfinite(getattr(station,n)) for n in ('radius_fraction','chord_ratio','thickness_ratio','pitch_factor')):
                raise ValueError('Radial distributions must be finite')
            if not 0 < station.radius_fraction <= 1:
                raise ValueError('Radial fractions must be in (0, 1]')
            if not 0 < station.chord_ratio < 1 or not 0 < station.thickness_ratio < .5 or station.pitch_factor <= 0:
                raise ValueError('Require 0 < c/D < 1, 0 < t/c < 0.5 and pitch factor > 0')
            if station.profile not in ('naca00', 'ellipse'):
                raise ValueError('Supported profiles: naca00, ellipse')
        radii = [s.radius_fraction for s in self.stations]
        if any(b <= a for a,b in zip(radii, radii[1:])) or radii[-1] != 1.0:
            raise ValueError('Radial stations must increase strictly and finish at r/R=1')
        if not radii[0] < self.hub_diameter_m / self.diameter_m:
            raise ValueError('Root station must be inside the hub radius for a connected solid')


def _sample(design, fraction):
    stations = design.stations
    r = [s.radius_fraction for s in stations]
    chord = float(np.interp(fraction,r,[s.chord_ratio for s in stations])) * design.diameter_m
    thickness = float(np.interp(fraction,r,[s.thickness_ratio for s in stations]))
    pd = float(np.interp(fraction,r,[s.pitch_factor for s in stations])) * design.pitch_ratio
    blend = float(np.interp(fraction,r,[float(s.profile == 'ellipse') for s in stations]))
    return chord, thickness, pd, blend


def section_coordinates(design: PropellerDesign, fraction: float) -> np.ndarray:
    """Closed polygon, no repeated endpoints; exact cylindrical radius r/R.

    Sections are developed onto cylinders rather than planar translations, so
    thickness and skew cannot accidentally enlarge the requested diameter.
    """
    if not isfinite(fraction) or not design.stations[0].radius_fraction <= fraction <= 1:
        raise ValueError('Section outside root-to-tip range')
    d = design.diameter_m
    radius = fraction*d/2
    chord, thickness, pd, blend = _sample(design, fraction)
    beta = atan2(pd*d, 2*pi*radius)
    x = .5*(1-np.cos(np.linspace(0,pi,design.section_points)))
    naca = 5*thickness*chord*(.2969*np.sqrt(x)-.1260*x-.3516*x**2+.2843*x**3-.1036*x**4)
    ellipse = .5*thickness*chord*np.sqrt(np.maximum(0,1-(2*x-1)**2))
    half = (1-blend)*naca + blend*ellipse
    half[[0,-1]] = 0  # closed leading/trailing edges, one vertex each
    x_loop = np.r_[x,x[-2:0:-1]]
    h_loop = np.r_[half,-half[-2:0:-1]]
    s = (x_loop-.5)*chord
    u = s*cos(beta)-h_loop*sin(beta)
    z = s*sin(beta)+h_loop*cos(beta)
    f = (fraction-design.stations[0].radius_fraction)/(1-design.stations[0].radius_fraction)
    if np.ptp(u/radius) >= 2*pi:
        raise ValueError("Section wraps around its cylinder; revise chord/pitch distribution")
    theta = u/radius + np.deg2rad(design.skew_deg)*f
    z += design.rake_m*f
    sign = 1 if design.handedness == 'right' else -1
    points = np.column_stack((radius*np.cos(theta), sign*radius*np.sin(theta), z))
    if not np.isfinite(points).all():
        raise ValueError('Geometry numerical range exceeded')
    return points


def _loft_blade(design):
    fractions = np.concatenate([np.linspace(a.radius_fraction,b.radius_fraction,
                  design.radial_subdivisions,endpoint=False)
                  for a,b in zip(design.stations,design.stations[1:])]+[np.array([1.])])
    sections = [section_coordinates(design,float(r)) for r in fractions]
    root = sections[0]
    if np.max(np.abs(root[:,2])) >= design.hub_length_m/2:
        raise ValueError('Hub too short to enclose the entire blade root; increase hub length')
    for fraction, ring in zip(fractions, sections):
        if fraction >= design.hub_diameter_m/design.diameter_m:
            # Angular chord extent must not meet the adjacent blade outside hub.
            angles = np.unwrap(np.arctan2(ring[:,1],ring[:,0]))
            if np.ptp(angles) >= 2*pi/design.blade_count:
                raise ValueError('Adjacent blades overlap outside the hub; reduce chord or blade count')
    vertices = np.vstack(sections)
    count = len(sections[0])
    faces = []
    for j in range(len(sections)-1):
        for k in range(count):
            a=j*count+k; b=j*count+(k+1)%count
            c=(j+1)*count+(k+1)%count; e=(j+1)*count+k
            faces.extend(((a,b,c),(a,c,e)))
    for index, fraction in ((0,fractions[0]),(len(sections)-1,1.)):
        f = (fraction-fractions[0])/(1-fractions[0])
        theta = np.deg2rad(design.skew_deg)*f
        radius=fraction*design.diameter_m/2
        center=[radius*cos(theta), (1 if design.handedness=='right' else -1)*radius*sin(theta),design.rake_m*f]
        center_index=len(vertices)
        vertices=np.vstack((vertices,center))
        for k in range(count):
            faces.append((center_index,index*count+k,index*count+(k+1)%count))
    mesh = trimesh.Trimesh(vertices,faces,process=True)
    mesh.fix_normals()
    return mesh


@dataclass
class PropellerGeometry:
    design: PropellerDesign
    mesh: trimesh.Trimesh
    hub: trimesh.Trimesh
    blades: tuple[trimesh.Trimesh, ...]

    @property
    def diameter_m(self):
        return float(2*np.linalg.norm(self.mesh.vertices[:,:2],axis=1).max())

    def solver_input(self):
        """Copy-only SI contract for future solvers; contains NO predicted KT/KQ."""
        self.validate()
        sections=[]
        for station in self.design.stations:
            radius=station.radius_fraction*self.design.diameter_m/2
            chord,thickness,pd,_=_sample(self.design,station.radius_fraction)
            sections.append(dict(radius_m=radius,chord_m=chord,thickness_ratio=thickness,
                pitch_m=pd*self.design.diameter_m,pitch_angle_rad=atan2(pd*self.design.diameter_m,2*pi*radius),
                profile=station.profile))
        return dict(units='m',shaft_axis=(0.,0.,1.),handedness=self.design.handedness,
                    vertices_m=self.mesh.vertices.copy(),triangles=self.mesh.faces.copy(),
                    sections=sections)

    def validate(self):
        report = mesh_report(self.mesh)
        if self.mesh.euler_number != 2:
            raise ValueError("Unexpected topological holes/handles in a solid-hub propeller")
        report["euler_characteristic"] = int(self.mesh.euler_number)
        report.update(diameter_m=self.diameter_m, blade_count=len(self.blades),
                      hub_diameter_m=float(2*np.linalg.norm(self.hub.vertices[:,:2],axis=1).max()))
        if not np.isclose(self.diameter_m,self.design.diameter_m,rtol=2e-6,atol=0):
            raise ValueError('Generated diameter differs from design')
        if not np.isclose(report["hub_diameter_m"],self.design.hub_diameter_m,rtol=2e-6,atol=0):
            raise ValueError("Generated hub diameter differs from design")
        if len(self.blades) != self.design.blade_count:
            raise ValueError('Blade count differs from design')
        return report


def mesh_report(mesh):
    if not isinstance(mesh,trimesh.Trimesh) or len(mesh.faces)==0 or not np.isfinite(mesh.vertices).all():
        raise ValueError('Nonempty finite triangle mesh required')
    if not mesh.is_watertight or not mesh.is_winding_consistent or not mesh.is_volume:
        raise ValueError('Mesh must be watertight, outward-oriented and enclose positive volume')
    if len(mesh.split(only_watertight=False)) != 1:
        raise ValueError('Export requires one connected solid')
    if not mesh.nondegenerate_faces(height=float(mesh.extents.max())*1e-12).all():
        raise ValueError('Degenerate triangles in mesh')
    return dict(watertight=True, outward_normals=True, connected_components=1,
                vertices=len(mesh.vertices), triangles=len(mesh.faces), volume_m3=float(mesh.volume))


def generate_propeller(design: PropellerDesign) -> PropellerGeometry:
    """Loft closed blade solids and robustly union with the hub using Manifold.

    Unit-size booleans improve numerical conditioning for model-scale geometry.
    Invalid lofts/unions are rejected, never exported as disconnected shells.
    """
    blade = _loft_blade(design)
    hub = trimesh.creation.cylinder(radius=design.hub_diameter_m/2,
                                    height=design.hub_length_m,sections=96)
    blades=[]
    for i in range(design.blade_count):
        copy=blade.copy()
        copy.apply_transform(trimesh.transformations.rotation_matrix(2*pi*i/design.blade_count,[0,0,1]))
        blades.append(copy)
    for component in (hub,*blades):
        mesh_report(component)
    normalized=[]
    for component in (hub,*blades):
        copy=component.copy(); copy.apply_scale(1/design.diameter_m); normalized.append(copy)
    try:
        solid=trimesh.boolean.union(normalized,engine='manifold',check_volume=True)
    except Exception as exc:
        raise ValueError(f'Blade/hub solid union failed: {exc}') from exc
    solid.apply_scale(design.diameter_m)
    result=PropellerGeometry(design,solid,hub,tuple(blades))
    result.validate()
    return result


def export_stl(geometry: PropellerGeometry, path, unit='mm'):
    """STL is unitless: explicitly select mm (printing) or m (CFD)."""
    geometry.validate()
    if unit not in ('mm','m'):
        raise ValueError('STL unit must be mm or m')
    path=Path(path)
    if path.suffix.lower() != '.stl':
        raise ValueError('Only genuine STL export is available; STEP is not implemented')
    mesh=geometry.mesh.copy()
    if unit=='mm': mesh.apply_scale(1000)
    payload=mesh.export(file_type='stl')
    reopened=trimesh.load_mesh(io.BytesIO(payload),file_type='stl',process=True)
    mesh_report(reopened)
    expected=geometry.design.diameter_m*(1000 if unit=='mm' else 1)
    if not np.isclose(2*np.linalg.norm(reopened.vertices[:,:2],axis=1).max(),expected,rtol=3e-6):
        raise ValueError('Exported STL dimension verification failed')
    path.write_bytes(payload)
    path.with_suffix('.stl.json').write_text(json.dumps(dict(units=unit,design=asdict(geometry.design)),indent=2),encoding='utf-8')


def save_design(design: PropellerDesign, path):
    Path(path).write_text(json.dumps(dict(schema_version=1,design=asdict(design)),indent=2),encoding='utf-8')


def load_design(path):
    document=json.loads(Path(path).read_text(encoding='utf-8'))
    if document.get('schema_version') != 1 or not isinstance(document.get('design'),dict):
        raise ValueError('Unsupported design schema')
    data=dict(document['design'])
    data['stations']=tuple(RadialStation(**s) for s in data['stations'])
    return PropellerDesign(**data)


def reference_designs():
    """Parametric examples only, not calibrated or experimentally validated propellers."""
    return (
        PropellerDesign(),
        PropellerDesign(diameter_m=.12,blade_count=4,hub_diameter_m=.028,hub_length_m=.036,pitch_ratio=1.0),
        PropellerDesign(diameter_m=.06,blade_count=2,hub_diameter_m=.014,hub_length_m=.020,pitch_ratio=.6,handedness='left'),
    )
