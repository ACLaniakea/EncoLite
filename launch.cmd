@echo off
setlocal
set "ENCOLITE_PY=%~dp0python\pythonw.exe"
if not exist "%ENCOLITE_PY%" set "ENCOLITE_PY=%~dp0.tools\python-3.13.17-embed-amd64\pythonw.exe"
if exist "%ENCOLITE_PY%" (
  start "" "%ENCOLITE_PY%" "%~dp0desktop_entry.py" %*
  exit /b 0
)
echo Python runtime was not found. Run tools/prepare_python.py and tools/prepare_qt.py. See README.md.
pause
exit /b 1
