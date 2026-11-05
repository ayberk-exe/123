# MarineProp Studio

**Research-stage, open-water marine propeller analysis** for small-scale models and ships.

> **Scientific limitation:** v0.1 does NOT infer KT or KQ from propeller geometry. You must provide open-water coefficients or measured data. The displayed default coefficients and downloadable CSV templates are synthetic, not experimentally validated. Do not use the output for safety-critical designs without independent verification.

## Features in v0.1

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
