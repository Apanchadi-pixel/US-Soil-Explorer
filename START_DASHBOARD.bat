@echo off
setlocal
cd /d "%~dp0"
REM Prefer PATH Python in Anaconda Prompt; otherwise find common Anaconda installations.
for %%P in ("%USERPROFILE%\anaconda3\python.exe" "%USERPROFILE%\Anaconda3\python.exe" "%LOCALAPPDATA%\anaconda3\python.exe" "C:\ProgramData\anaconda3\python.exe" "%USERPROFILE%\miniconda3\python.exe") do (
  if exist %%P (
    "%%~P" server.py
    goto done
  )
)
where python >nul 2>nul
if not errorlevel 1 (
  python server.py
  goto done
)
echo Python was not found. Open ANACONDA PROMPT, change to this folder, and run: python server.py
echo You do not need to reinstall Python.
:done
if errorlevel 1 pause
endlocal
