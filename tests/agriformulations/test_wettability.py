"""Analytical benchmarks and saved recipe linkage for wettability scenarios."""
import math
import pytest
from agri_tool import execute
from agriformulations.rnd import simulation_catalog
from agriformulations.rnd.wettability import predict

BASE={'surface_tension_mn_m':72,'solid_vapor_tension_mn_m':72,'solid_liquid_tension_mn_m':0,
      'viscosity_mpa_s':1,'pore_radius_um':10,'penetration_distance_mm':1,
      'dynamic_initial_angle_deg':90,'contact_line_speed_mm_s':0.001,'macro_micro_ratio':100,
      'surfactant_mol_l':0,'langmuir_k_l_mol':100,'max_surface_tension_reduction_fraction':0,
      'roughness_ratio':1,'porosity_fraction':0.2,'droplet_diameter_mm':1}

def test_young_equation_complete_wetting_benchmark():
    out=predict(BASE)
    assert out['metrics']['equilibrium_contact_angle_deg']==pytest.approx(0,abs=1e-6)

def test_young_laplace_and_washburn_known_values():
    out=predict(BASE)['metrics']
    assert out['young_laplace_pressure_pa']==pytest.approx(14400,rel=1e-6)
    expected=2*.001*(.001**2)/(.00001*.072)
    assert out['washburn_penetration_time_s']==pytest.approx(expected,rel=1e-6)

def test_langmuir_adsorption_half_coverage():
    p=dict(BASE,surfactant_mol_l=.01,langmuir_k_l_mol=100)
    assert predict(p)['metrics']['langmuir_surface_coverage_fraction']==pytest.approx(.5)

def test_dynamic_angle_rejects_out_of_domain_capillary_number():
    with pytest.raises(ValueError,match='capillary number'):
        predict(dict(BASE,contact_line_speed_mm_s=10000))

def test_catalogue_and_saved_run_use_existing_recipe(tmp_path):
    spec=simulation_catalog.spec('wettability')
    assert spec['metric']=='equilibrium_contact_angle_deg'
    recipe={'name':'Wetting baseline','format':'SC','batch_g':100,'ingredients':[
      {'name':'Active X','role':'active','pct':10,'purity_pct':100}, {'name':'Water','role':'solvent','pct':90}]}
    made=execute({'operation':'recipes','action':'manual','payload':{'recipe':recipe}},tmp_path)
    pid=made['project_id'];rid=made['result']['recipes'][0]['recipe_id']
    ran=execute({'operation':'simulate','action':'run','model':'wettability','project_id':pid,
       'payload':{'recipe_id':rid,'inputs':dict(BASE,solid_liquid_tension_mn_m=36)}},tmp_path)
    assert ran['status']=='completed', ran
    assert ran['result']['result']['recipe_linkage']['recipe_id']==rid
    assert ran['result']['result']['evidence']=='assumed scenario'
    loaded=execute({'operation':'project','action':'result','project_id':pid,
        'payload':{'id':ran['result']['scenario_id']}},tmp_path)
    assert loaded['status']=='completed', loaded
    assert loaded['result']['record']==ran['result']
