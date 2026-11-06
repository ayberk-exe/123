# MarineProp Studio

**Research-stage, open-water marine propeller analysis** for small-scale models and ships.

> **Scientific limitation:** v0.1 does NOT infer KT or KQ from propeller geometry. You must provide open-water coefficients or measured data. The displayed default coefficients and downloadable CSV templates are synthetic, not experimentally validated. Do not use the output for safety-critical designs without independent verification.

## Hydrodynamic application features

- SI-units open-water calculations: advance coefficient J, thrust T, torque Q, shaft power and open-water efficiency
- Interactive Streamlit interface in Turkish
- Coefficient curve plotting from CSV containing `J,KT,KQ`
- Linear interpolation *inside* measured J range; extrapolation is prohibited
- Experimental CSV conversion to nondimensional coefficients, using `rpm,advance_speed_m_s,thrust_n,torque_nm`
- Export calculation and curve results as CSV
- Pytest unit tests for reference arithmetic, interpolation and edge conditions

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/ayberk-exe/123.git
cd 123
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

In Codex cloud, use the repository as the project, install `requirements.txt`, and execute the same pytest command.

## Open-water physics

`J = VA/(n D)`, `T = KT rho n² D⁴`, `Q = KQ rho n² D⁵`,
`Pshaft = 2 pi n Q`, `eta0 = J KT/(2 pi KQ)`, with `n = RPM/60`.

`eta0` is undefined for zero RPM or nonpositive KQ; negative KT also suppresses efficiency in this model. At zero RPM the dimensional definitions yield zero thrust and torque, **not** a physical prediction of windmilling behavior.

All inputs are SI units; CSV templates are illustrative only.

## Planned milestones

1. Documented Wageningen B-Series regression **only after** coefficients and applicability limits are verified.
2. Propeller geometry definitions and optional CAD export.
3. BEMT and blade Reynolds-number assessment for model-scale operation.
4. Thruster–hull–motor matching for ITU Green Ship, supported by real experimental curves.
5. OpenFOAM validation against benchmark datasets, including mesh convergence.
6. Constrained multiobjective optimization.

## Testing and validation

`pytest` covers numerical identities and input constraints. Passing unit tests is **verification of implementation**, not experimental validation of a propeller model. No B-Series or CFD validation claim is made.

## Next step for Codex

Run the tests and launch the Streamlit UI. Fix reported execution errors before adding features. Add a documented published propeller model only with verified scientific coefficients and references.

## Development update

The original application now has six Turkish/English engineering sections:
Dashboard, performance, open-water curves, comparison, experiments, and settings.
The coefficient CSV exports dimensional T/Q/shaft-power curves at fixed RPM and
D, varying advance speed with J. Two propellers can be compared at the same
advance speed; their KT/KQ inputs must correspond to their respective J and Re.

Viscosity is kinematic viscosity in m²/s. `Re_n = n D² / nu` is a rotational
reference number, not a blade Reynolds number. The optional section assessment
uses `Re_0.7R = c_0.7R sqrt(VA² + (0.7 pi n D)²) / nu`, without induced velocity.
Neither calculation supplies a transition criterion or empirical scale correction.
Model-scale use displays an explicit Reynolds warning. Fluid values are user
inputs; temperature/salinity property prediction is not implemented.

`marineprop/data.py` centralizes measured CSV conversion. `marineprop/vessel.py`
provides validated forward-operation sample and twin-thruster project contracts,
including optional electrical power, motor efficiency, resistance and interaction
inputs. The ITU Green Ship project contains **no T60 measurements**. These schemas
do not predict vessel equilibrium or automatically sum unmatched operating points.

Future implementations should remain separate modules consuming the SI core:
BEMT, cavitation, motor matching, CFD adapters, optimization and reports.
These solvers are not operational. Parametric geometry and validated STL are now
available in the separate v0.2 desktop application; STEP remains unavailable. Wageningen coefficients remain absent
until published coefficients, provenance and applicability limits are verified.

Verification: `python -m pytest -q` exercises arithmetic, scaling, Reynolds,
CSV round trips, invalid measurements, project contracts, and Streamlit AppTest
rendering/recalculation plus valid and invalid CSV paths. Uploaded-file widgets
are substituted with in-memory CSV streams in UI tests; physical browser upload
and download interactions have not been tested. This is numerical/software
verification, not scientific validation against experiments or CFD.

Recommended next milestone: obtain traceable T60 open-water and electrical
measurements with uncertainty, geometry and fluid conditions; validate repeatable
model-scale performance before motor/hull matching or empirical models.

## Engineering audit repair

See [audit and limitations](docs/ENGINEERING_AUDIT.md) and the
[native Windows migration plan](docs/DESKTOP_MIGRATION.md).
The primary analysis now explicitly selects A (user coefficients), B (imported
experimental curve, measured-range interpolation only), or unavailable C (series).
B never falls back to synthetic coefficients when data are missing/out of range.
Exports include validity status; impossible efficiencies are retained and flagged.
Optional measured `electrical_power_w` and `motor_efficiency` CSV columns are
preserved. Shaft/electrical ratio is distinct from motor-only efficiency.

The optional actual-browser test is `python scripts/browser_smoke.py --url
http://127.0.0.1:8502`, with Streamlit running on that port and Playwright plus an
installed Chromium supplied separately. It is not needed to run the application.
For Windows use the existing `.venv` as described in the migration document.

## v0.2 — Parametric native 3D designer

`desktop_app.py` launches a separate **PySide6 + PyVista/VTK** application.
Generate and inspect real radial-section propeller meshes; edit blade count,
pitch/chord/thickness distributions, profiles, rake/skew and handedness; save
JSON and export validated, connected STL in mm or m. STEP is not implemented.
Geometry does not predict hydrodynamic performance.

Use a separate Python 3.12 `.venv-cad` and `requirements-desktop.txt`; preserve
the existing `.venv`. See the [desktop guide](docs/DESKTOP_V02.md) for Windows
commands, mathematics, acceptance evidence, limitations and packaging path.
Three parametric examples are in `examples/designs/`.
