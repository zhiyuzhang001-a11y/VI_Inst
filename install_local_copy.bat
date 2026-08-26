@echo off
setlocal
cd /d "%~dp0"
set "TARGET=%LOCALAPPDATA%\VI_Inst_App"

echo This copies only program files to:
echo %TARGET%
echo Measurement data and config.local.toml are not copied.
echo.

if not exist "%TARGET%" mkdir "%TARGET%"
if not exist "%TARGET%\waveform" mkdir "%TARGET%\waveform"

for %%F in (
    2400_Hall_plot.py Hall_plot.py SMR_plot.py address.py app_config.py
    check_environment.py config.toml keithley_2400.py keithley_6221_pdel.py
    keithley_iv.py launcher.py live_plot_process.py magnet_control.py
    requirements.txt sequence_pdel_monitor.py set_H.py static_plot.py
    sweep_angle.py switch_plot.py README.md setup_windows.bat run_windows.bat
) do copy /y "%%F" "%TARGET%\%%F" >nul

copy /y "waveform\sinesqr_1.py" "%TARGET%\waveform\sinesqr_1.py" >nul

echo Program files copied successfully.
echo Starting installation in the local folder...
pushd "%TARGET%"
call setup_windows.bat
popd
exit /b %errorlevel%
