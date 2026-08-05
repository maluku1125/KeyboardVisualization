@echo off
cd /d "%~dp0"

echo === Build Key Visualizer exe ===

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller. Check that pip works.
        pause
        exit /b 1
    )
)

python -m PyInstaller --onefile --noconsole --name KeyVisualizer --clean key_visualizer.py
if errorlevel 1 (
    echo [ERROR] Build failed. Copy the error message above to Claude.
    pause
    exit /b 1
)

if exist config.json copy /y config.json dist\config.json >nul

echo.
echo Done! Output: dist\KeyVisualizer.exe
echo config.json was copied next to the exe.
pause
