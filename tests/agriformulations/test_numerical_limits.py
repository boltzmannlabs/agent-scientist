"""Independent limits for the numerical engine shipped with the tool."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
from scipy.special import hyp2f1, jn_zeros


from agriformulations.physics.geometry import analytic_release_fraction
from agriformulations.physics.swelling import effective_tau
from agriformulations.rnd.simulation_models import run
from agriformulations.surrogate.models import MondrianConformal
from agriformulations.surrogate.evaluate import run_leave_one_study_out
from agriformulations.surrogate.features import SUMMARY_TARGETS


def test_diffusion_has_no_truncation_burst_and_matches_resolved_series():
    tiny = np.array([0., 8.64e-21, 1e-14])
    for geometry, surface_factor in [("slab", 2), ("cylinder", 4), ("sphere", 6)]:
        actual = analytic_release_fraction(tiny, geometry)
        assert actual[0] == 0
        assert actual[1:] == pytest.approx(surface_factor * np.sqrt(tiny[1:] / np.pi), rel=1e-6)
        assert analytic_release_fraction(0., geometry) == 0
        assert analytic_release_fraction([], geometry).size == 0
    times = np.array([9.99e-6, 1e-5, 1.001e-5, .001, .1])
    zeros = jn_zeros(0, 10000)
    independently_resolved = 1 - np.sum(4 / zeros**2 * np.exp(-times[:, None] * zeros**2), axis=1)
    assert analytic_release_fraction(times, "cylinder", modes=1) == pytest.approx(independently_resolved, abs=1e-12)
    slab_times = np.array([.00999, .01, .01001, .1])
    n = np.arange(1, 20000, 2)
    slab_reference = 1 - np.sum(8 / (np.pi * n)**2 * np.exp(-slab_times[:, None] * (np.pi * n / 2)**2), axis=1)
    assert analytic_release_fraction(slab_times, "slab", modes=1) == pytest.approx(slab_reference, abs=1e-12)
    for bad in [-1, np.nan, np.inf]:
        with pytest.raises(ValueError):
            analytic_release_fraction([bad], "slab")


def test_swelling_clock_matches_closed_forms_and_is_horizon_independent():
    times = np.array([36500., 0., .001, 30., .001])
    for k in [0., .1, 1000.]:
        actual = effective_tau(times, rate=.7, swelling_rate=k, swelling_exponent=1)
        assert actual == pytest.approx(.7 * times / (1 + k * times), rel=1e-12, abs=1e-15)
    for exponent, k, horizon in [(0.05,1000.,36500.), (.5,1000.,30.), (3.,1000.,36500.), (.1,.1,.1), (.5,.1,30.)]:
        actual = effective_tau([0., horizon], rate=1., swelling_rate=k, swelling_exponent=exponent)[-1]
        # This hypergeometric antiderivative is independent of the production
        # natural-timescale/log-time quadrature and includes fractional powers.
        reference = horizon * hyp2f1(2, 1/exponent, 1+1/exponent, -k * horizon**exponent)
        assert actual == pytest.approx(reference, rel=1e-9, abs=1e-13)
        together = effective_tau([.001,horizon], rate=1., swelling_rate=k, swelling_exponent=exponent)[0]
        alone = effective_tau([.001], rate=1., swelling_rate=k, swelling_exponent=exponent)[0]
        assert together == alone
    p = dict(geometry="sphere", diffusivity_m2_s=1e-16, length_um=50, horizon_days=30,
             swelling_rate=1000, swelling_exponent=1)
    actual = run("swelling_release", p)["metrics"]["release_at_horizon"]
    tau = 1e-16 * 86400 / (50e-6)**2 * 30 / 30001
    reference = 6 * np.sqrt(tau/np.pi) - 3*tau
    assert actual == pytest.approx(reference, rel=1e-12)


def test_conformal_order_statistic_counts_independent_units():
    residuals = pd.Series(np.arange(1.,10.))
    conformal = MondrianConformal(.1).calibrate(residuals, pd.Series(["a"]*9), pd.Series([1.]*9))
    assert conformal.interval_half_width("a",1.) == 9.
    assert np.isinf(conformal.interval_half_width("unseen",1.))
    # Nine correlated curves from one study remain one calibration unit.
    clustered = MondrianConformal(.1).calibrate(residuals, pd.Series(["a"]*9), pd.Series([1.]*9), units=pd.Series(["one-study"]*9))
    assert clustered.unit_counts["a"] == 1
    assert np.isinf(clustered.interval_half_width("a",1.))
    assert np.isinf(MondrianConformal().interval_half_width("a",1.))
    with pytest.raises(ValueError):
        conformal.calibrate(residuals, pd.Series(["a"]*9), pd.Series([0.]*9))


def test_loso_does_not_report_finite_confidence_from_one_calibration_study():
    rows, observations = [], {}
    for study in ["s1", "s2", "s3"]:
        for i in range(10):
            x = .1 + i / 10
            cid = study + "_" + str(i)
            rows.append(dict(study_key=study,study_id=study,data_source="literature",curve_id=cid,
                formulation_id="f"+str(i),condition_id="one",unit="%",unit_family="percent",scale_to_native=100.,
                end_time_native=10+x,time_unit="h",weibull_tau_time=5+x,weibull_beta=.8+x,
                endpoint_fraction=.5+.1*x,t50_time=2+x,ph=7.,temperature_c=25.,finite_bath_factor=1.,
                calibrated_rate=.01*x,geometry_tag="sphere",assay_type="release",sink_condition="sink"))
            observations[cid] = pd.DataFrame({"time":[0.,1.,2.],"value":[0.,10.,20.]})
    summaries = pd.DataFrame(rows)
    first = run_leave_one_study_out(summaries, observations)
    assert first["coverage_rate"] is None
    assert first["coverage"]["covered"].isna().all()
    assert first["coverage"]["half_width"].isna().all()
    assert set(first["coverage"]["independent_calibration_units"]) == {1}
    edited = summaries.copy()
    edited.loc[edited.study_key=="s3",list(SUMMARY_TARGETS)] *= 100
    second = run_leave_one_study_out(edited, observations)
    # Held-out targets cannot affect the interval center or prediction scale.
    a = first["coverage"].query("study_id == 's3'")
    b = second["coverage"].query("study_id == 's3'")
    np.testing.assert_allclose(a["point"],b["point"],rtol=0,atol=0)
