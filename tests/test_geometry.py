"""Geometry verification, independent of Streamlit and any GUI display."""
from dataclasses import replace
import json
from math import atan2, pi

import numpy as np
import pytest

pytest.importorskip('trimesh',reason='Install requirements-desktop.txt in the separate CAD environment')
pytest.importorskip('manifold3d')
import trimesh
from marineprop.geometry import (
    PropellerDesign, RadialStation, export_stl, generate_propeller, load_design,
    mesh_report, reference_designs, save_design, section_coordinates,
)


@pytest.fixture(scope='module')
def references():
    return tuple(generate_propeller(d) for d in reference_designs())


def test_reference_diameters_blades_hubs_spacing_and_solids(references):
    for g in references:
        report=g.validate()
        assert report['diameter_m']==pytest.approx(g.design.diameter_m,rel=2e-6)
        assert report['hub_diameter_m']==pytest.approx(g.design.hub_diameter_m)
        assert len(g.blades)==g.design.blade_count
        for i,blade in enumerate(g.blades):
            rotation=trimesh.transformations.rotation_matrix(2*pi*i/g.design.blade_count,[0,0,1])
            expected=trimesh.transform_points(g.blades[0].vertices,rotation)
            np.testing.assert_allclose(blade.vertices,expected,atol=1e-14)
            assert blade.is_watertight and blade.is_winding_consistent and blade.volume>0
        assert g.mesh.is_watertight and g.mesh.is_winding_consistent
        assert len(g.mesh.split())==1
        assert g.mesh.volume>g.hub.volume
        assert np.isfinite(g.mesh.face_normals).all()
        assert len(g.mesh.edges_unique)==len(g.mesh.edges_unique_length)
        _,counts=np.unique(g.mesh.edges_unique_inverse,return_counts=True)
        assert (counts==2).all()


def test_three_to_four_and_pitch_changes(references):
    d=references[0].design
    four=generate_propeller(replace(d,blade_count=4))
    changed=generate_propeller(replace(d,pitch_ratio=1.1))
    assert len(four.blades)==4
    assert four.mesh.volume>references[0].mesh.volume
    assert not np.allclose(changed.blades[0].vertices,references[0].blades[0].vertices)
    assert changed.validate()['diameter_m']==pytest.approx(.08,rel=2e-6)


def test_developed_pitch_chord_and_cylindrical_radius():
    d=PropellerDesign(rake_m=.004,skew_deg=25)
    stations=tuple(replace(s,pitch_factor=.7+.5*s.radius_fraction) for s in d.stations)
    d=replace(d,stations=stations)
    for s in stations:
        ring=section_coordinates(d,s.radius_fraction)
        radius=s.radius_fraction*d.diameter_m/2
        np.testing.assert_allclose(np.linalg.norm(ring[:,:2],axis=1),radius,atol=1e-14)
        leading,trailing=ring[0],ring[d.section_points-1]
        angles=np.unwrap(np.arctan2(ring[:,1],ring[:,0]))
        tangential=radius*(angles[d.section_points-1]-angles[0])
        axial=trailing[2]-leading[2]
        assert axial/tangential==pytest.approx(d.pitch_ratio*s.pitch_factor*d.diameter_m/(2*pi*radius))
        assert np.hypot(axial,tangential)==pytest.approx(s.chord_ratio*d.diameter_m)


def test_handedness_rake_skew_and_profile(references):
    d=references[0].design
    left=generate_propeller(replace(d,handedness='left'))
    for station in d.stations:
        np.testing.assert_allclose(section_coordinates(left.design,station.radius_fraction),
            section_coordinates(d,station.radius_fraction)*np.array([1,-1,1]),atol=1e-14)
    expected=references[0].blades[0].vertices*np.array([1,-1,1])
    # Trimesh processing may reindex reflected vertices; compare point clouds sorted.
    np.testing.assert_allclose(np.sort(left.blades[0].vertices,axis=0),np.sort(expected,axis=0),atol=1e-14)
    assert left.mesh.volume==pytest.approx(references[0].mesh.volume,rel=1e-5)
    base=section_coordinates(d,1)
    rake=section_coordinates(replace(d,rake_m=.005),1)
    np.testing.assert_allclose(rake[:,2]-base[:,2],.005)
    skew=section_coordinates(replace(d,skew_deg=d.skew_deg+10),1)
    rot=trimesh.transformations.rotation_matrix(np.deg2rad(10),[0,0,1])
    np.testing.assert_allclose(skew,trimesh.transform_points(base,rot),atol=1e-14)
    ellipse=replace(d,stations=tuple(replace(s,profile='ellipse') for s in d.stations))
    assert not np.allclose(section_coordinates(ellipse,.6),section_coordinates(d,.6))
    assert generate_propeller(ellipse).validate()['watertight']


@pytest.mark.parametrize('change', [
    {'diameter_m':0},{'hub_diameter_m':.09},{'hub_diameter_m':0},
    {'blade_count':0},{'blade_count':3.5},{'pitch_ratio':0},
    {'diameter_m':float('nan')},{'rake_m':float('inf')},
    {'skew_deg':90},{'handedness':'unknown'}, {'section_points':3},
])
def test_invalid_parameters(change):
    with pytest.raises(ValueError): PropellerDesign(**change)


@pytest.mark.parametrize('field,value', [('thickness_ratio',0),('thickness_ratio',-.1),('chord_ratio',0),('pitch_factor',0),('profile','invented')])
def test_invalid_sections(field,value):
    d=PropellerDesign()
    with pytest.raises(ValueError):
        replace(d,stations=(replace(d.stations[0],**{field:value}),*d.stations[1:]))


def test_invalid_root_tip_hub_length_and_overlap():
    d=PropellerDesign()
    with pytest.raises(ValueError,match='root|Root'):
        replace(d,stations=(replace(d.stations[0],radius_fraction=.3),*d.stations[1:]))
    with pytest.raises(ValueError,match='finish'):
        replace(d,stations=(*d.stations[:-1],replace(d.stations[-1],radius_fraction=.99)))
    with pytest.raises(ValueError,match='Hub too short'):
        generate_propeller(replace(d,hub_length_m=.001))
    with pytest.raises(ValueError,match='overlap'):
        generate_propeller(replace(d,blade_count=12,hub_length_m=.1,stations=tuple(replace(s,chord_ratio=.9) for s in d.stations)))


def test_invalid_mesh_is_rejected():
    mesh=trimesh.creation.box()
    mesh.update_faces(np.arange(len(mesh.faces)-1))
    with pytest.raises(ValueError,match='watertight'): mesh_report(mesh)
    disconnected=trimesh.util.concatenate([trimesh.creation.box(),trimesh.creation.box(transform=trimesh.transformations.translation_matrix([3,0,0]))])
    with pytest.raises(ValueError,match='connected'): mesh_report(disconnected)
    inverted=trimesh.creation.box(); inverted.invert()
    with pytest.raises(ValueError,match='outward'): mesh_report(inverted)


def test_stl_export_units_reopen_and_json_roundtrip(references,tmp_path):
    for index,g in enumerate(references):
        path=tmp_path/f'propeller_{index}.stl'
        export_stl(g,path,'mm')
        reopened=trimesh.load_mesh(path,process=True)
        mesh_report(reopened)
        assert 2*np.linalg.norm(reopened.vertices[:,:2],axis=1).max()==pytest.approx(g.design.diameter_m*1000,rel=3e-6)
        assert json.loads(path.with_suffix('.stl.json').read_text())['units']=='mm'
        export_stl(g,path,'m')
        assert trimesh.load_mesh(path).volume==pytest.approx(g.mesh.volume,rel=1e-5)
        design_path=tmp_path/f'design_{index}.json'
        save_design(g.design,design_path)
        assert load_design(design_path)==g.design
    with pytest.raises(ValueError,match='STEP'): export_stl(references[0],tmp_path/'fake.step')


def test_independent_vtk_stl_reader(references,tmp_path):
    pv=pytest.importorskip('pyvista')
    path=tmp_path/'vtk_check.stl'; export_stl(references[0],path,'mm')
    read=pv.read(path).clean()
    assert read.n_open_edges==0
    assert read.n_cells>100
    np.testing.assert_allclose(2*np.linalg.norm(read.points[:,:2],axis=1).max(),80,rtol=3e-6)
    assert read.volume==pytest.approx(references[0].mesh.volume*1e9,rel=1e-5)
    assert np.unique(read.connectivity()['RegionId']).size==1


def test_solver_contract_has_si_geometry_no_empirical_prediction(references):
    g=references[0]
    contract=g.solver_input()
    assert contract['units']=='m' and contract['shaft_axis']==(0,0,1)
    assert 'KT' not in contract and 'KQ' not in contract
    assert contract['sections'][-1]['radius_m']==.04
    contract['vertices_m'][0]=0
    assert not np.array_equal(contract['vertices_m'],g.mesh.vertices)


def test_section_thickness_and_profile_distribution():
    from marineprop.geometry import _sample
    d=PropellerDesign(section_points=100)
    for station in d.stations:
        ring=section_coordinates(d,station.radius_fraction)
        radius=station.radius_fraction*d.diameter_m/2
        beta=atan2(d.pitch_ratio*station.pitch_factor*d.diameter_m,2*pi*radius)
        f=(station.radius_fraction-d.stations[0].radius_fraction)/(1-d.stations[0].radius_fraction)
        u=(np.unwrap(np.arctan2(ring[:,1],ring[:,0]))-np.deg2rad(d.skew_deg)*f)*radius
        z=ring[:,2]-d.rake_m*f
        h=-u*np.sin(beta)+z*np.cos(beta)
        # Closed-TE NACA polynomial reaches requested t/c to ~0.1% discretization.
        assert np.ptp(h)==pytest.approx(station.thickness_ratio*station.chord_ratio*d.diameter_m,rel=.002)
        assert _sample(d,station.radius_fraction)[2]==pytest.approx(d.pitch_ratio*station.pitch_factor)
    thicker=replace(d,stations=tuple(replace(s,thickness_ratio=1.2*s.thickness_ratio) for s in d.stations))
    assert not np.allclose(section_coordinates(thicker,.6),section_coordinates(d,.6))


def test_chord_variation_and_root_tip_caps(references):
    g=references[0]
    d=replace(g.design,stations=tuple(replace(s,chord_ratio=.9*s.chord_ratio) for s in g.design.stations))
    narrower=generate_propeller(d)
    assert narrower.mesh.volume<g.mesh.volume
    assert narrower.blades[0].is_watertight
    radii=np.linalg.norm(narrower.blades[0].vertices[:,:2],axis=1)
    assert radii.max()==pytest.approx(d.diameter_m/2)
    assert radii.min()<d.hub_diameter_m/2
