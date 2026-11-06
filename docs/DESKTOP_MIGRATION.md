# Native Windows migration plan

Proceed after measurement-based engineering validation; keep Streamlit operational
while migrating. Do not introduce a Qt dependency into this repair.

1. Freeze the independently tested `marineprop.core`, `data` and `vessel` contracts
   and CSV/status semantics. None imports Streamlit. Add traceable real-data
   benchmarks and uncertainty propagation before a predictive model is introduced.
2. Extract UI presentation into a framework-neutral application service returning
   results, provenance and validity diagnostics. Preserve signed quantities and
   distinguish missing, invalid and unavailable predictions.
3. Add a separate PySide6 entrypoint, with model/view tables and SI conversion at
   display boundaries. Provide explicit methods A/B/C; leave unavailable solvers
   unavailable. Run file operations and future CFD jobs off the GUI thread.
4. Implement offline project persistence with versioned JSON/CSV schemas, atomic
   saves and explicit migrations. Bundle icons, fonts and documentation locally;
   avoid CDN/network dependencies. Never bundle credentials or synthetic T60 data
   as real measurements.
5. Reuse the numerical suite, then add Qt widget tests and Windows end-to-end file,
   locale/decimal separator, Unicode-path, high-DPI and offline tests. Compare the
   desktop and Streamlit results for the same benchmark inputs.
6. Build an isolated, pinned Windows release environment. Evaluate PyInstaller
   for distribution and Inno Setup/MSIX for installation; verify Qt licensing,
   dependency licenses, code signing, clean-machine installation, uninstall,
   user-data preservation and reproducible release hashes before release.

Windows verification for this Streamlit version (existing virtual environment):

```powershell
Set-Location 'C:\Users\ayber\OneDrive\Desktop\MarineProp-Studio'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If dependencies need refreshing, use only the existing environment:
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
Do not delete/recreate the environment or use global pip. These Windows commands
are documented for the user; they have not been executed from the Linux cloud.
