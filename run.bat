@echo off
cd /d "%~dp0"
python key_visualizer.py
if errorlevel 1 pause
