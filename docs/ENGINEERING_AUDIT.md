# Engineering audit and verification

Audited baseline: `30791a7`, repository main. The user's Windows files were
confirmed to match GitHub. Execution was on Linux in the cloud, not on the local
Windows virtual environment. No Windows environment was changed, deleted or tested.
All source/test files, requirements and README were inspected. SciPy is not a
current dependency and is unnecessary for linear interpolation.

## Independent dimensional check

With n = RPM / 60 in s⁻¹:

| Quantity | Definition | Units |
|---|---|---|
| J | VA/(n D) | dimensionless |
| KT | T/(rho n² D⁴) | dimensionless |
| KQ | Q/(rho n² D⁵) | dimensionless; NOT 10KQ |
| T | KT rho n² D⁴ | kg m s⁻² = N |
| Q | KQ rho n² D⁵ | kg m² s⁻² = N m |
| Pshaft | 2 pi n Q | kg m² s⁻³ = W |
| eta0 | T VA/Pshaft = J KT/(2 pi KQ) | dimensionless |
| Re_n | n D²/nu | dimensionless |
| Re_0.7R | c sqrt(VA² + (0.7 pi n D)²)/nu | dimensionless |

The section velocity is geometric, omitting induction, swirl and wake. The
rotational Re convention does not include pi; it must not be compared to a
section-Re validity threshold. Neither Reynolds diagnostic constitutes a
transition model or empirical scale correction.

Independent full-scale arithmetic: D=2 m, n=2 s⁻¹, rho=1025 kg/m³,
KT=.2, KQ=.04 gives T=13120 N, Q=5248 N m and P=4 pi * 5248 W.
At VA=0 efficiency is zero, despite nonzero bollard thrust. Unit tests also verify
model-scale arithmetic, dimensional scaling and inverse measurement conversion.

## Defects reproduced and repaired

- Experimental curve evaluation was separate from the primary performance result.
  Methods A and B are now explicitly selectable. B uses measured-range linear
  interpolation and refuses missing data, zero RPM and extrapolation, without
  silently substituting A. C explicitly produces no result.
- eta > 1 was warned only in the direct view. Shared regime flags now appear in
  comparisons, curve and measurement exports and UI warnings. Raw eta is retained
  for diagnosis; clipping would hide bad measurements. Negative coefficients
  retain signed T/Q but suppress forward-propulsion efficiency.
- Electrical CSV columns were discarded. Optional electrical_power_w and
  motor_efficiency are preserved and validated. The measured shaft/electrical
  ratio is exported separately, not mislabeled as motor-only efficiency.
  Shaft power exceeding electrical input is flagged. No missing efficiency is
  assumed and no T60 measurements are generated.
- Finite but extreme inputs could raise uncaught OverflowError or return nonfinite
  results. Dimensional scales and derived quantities now reject overflow and
  denominator underflow with a user-readable numeric-range error.
- Nested coefficient arrays were indexed before dimensional validation. Shape
  validation now runs first.
- Curve arithmetic was duplicated inside Streamlit. It now shares the calculation
  engine, including undefined efficiency at zero RPM and status reporting.
- Streamlit deprecated width calls were replaced; minimum Streamlit is 1.49 for
  the APIs used. Downloads now use on_click='ignore' to avoid unnecessary reruns.
- A standalone property used for range checking was rendered by Streamlit's magic;
  it is now assigned to an internal variable.

Zero RPM returns zero dimensional outputs only by the supplied-coefficient
scaling definition. It is not a windmilling/locked-propeller prediction.

## Evidence and limits

The baseline suite actually executed: 13 passed. The repaired suite covers
invalid/nonfinite inputs, zero RPM, static thrust, signed coefficients,
impossible efficiency, overflow/underflow, Reynolds, CSV, energy accounting,
interpolation/no extrapolation, six UI sections and input recalculation.
Run `python -m pytest -q` for the current count.

`scripts/browser_smoke.py` is an optional Playwright/Chromium check (not an app
dependency). With Streamlit running, it visits all six rendered tabs, uploads
coefficient and electrical measurement CSVs, selects method B, verifies thrust,
checks CSV/JSON download contents, uploads a malformed CSV and checks JS errors.
Use `--chromium` to select an installed Chromium binary. It uses clearly synthetic
fixtures for software verification, never as measured hydrodynamic evidence.

No real propeller data, uncertainty analysis, CFD comparison or published series
validation was performed. Geometry cannot predict coefficients here. Users must
supply traceable KT/KQ or experimental curves for the same geometry and relevant
Reynolds conditions. The application cannot establish applicability from J alone.
Project Settings is a data-schema preview/export, not a calibrated vessel model.
The two T60 datasets are empty. Electrical import is per measurement dataset;
automatic port/starboard matching and vessel equilibrium remain future work.

Final executed outcome for this repair: `python -m pytest -q` returned **48 passed**
(one third-party anyio/pytest deprecation warning). The actual Chromium script
passed after repair, including all seven CSV/JSON download buttons available with
both datasets loaded. Main page and health endpoint returned HTTP 200. These
outcomes apply to the cloud instance; Windows execution remains unverified.
