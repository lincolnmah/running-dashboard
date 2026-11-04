@echo off
REM Double-click to export your Garmin data into the garmin_export folder.
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install --quiet --upgrade gcpapi-sync
%PY% garmin_export.py %*
pause
