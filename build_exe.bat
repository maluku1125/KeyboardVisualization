@echo off
cd /d "%~dp0"

echo ============================================
echo  Build Key Visualizer  (folder + single)
echo ============================================
echo.

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

echo [1/2] Folder build (antivirus-friendly, recommended)...
python -m PyInstaller --onedir --noconsole --name KeyVisualizer --clean --noconfirm key_visualizer.py
if errorlevel 1 (
    echo [ERROR] Folder build failed. Copy the error message above to Claude.
    pause
    exit /b 1
)

echo.
echo [2/2] Single-file build (portable, more AV false positives)...
python -m PyInstaller --onefile --noconsole --name KeyVisualizer_single --noconfirm key_visualizer.py
if errorlevel 1 (
    echo [ERROR] Single-file build failed.
    pause
    exit /b 1
)

if exist config.json copy /y config.json dist\KeyVisualizer\config.json >nul

REM ---- package the folder build into a zip for uploading ----
echo.
echo Zipping folder build...
if exist dist\KeyVisualizer.zip del /q dist\KeyVisualizer.zip
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\KeyVisualizer' -DestinationPath 'dist\KeyVisualizer.zip' -CompressionLevel Optimal -Force"
if errorlevel 1 (
    echo [WARN] Zip failed. Compress the dist\KeyVisualizer folder manually.
) else (
    echo Zip created: dist\KeyVisualizer.zip
)

echo.
echo ============================================
echo  Done. Upload these two:
echo    dist\KeyVisualizer.zip          (folder build - recommended)
echo    dist\KeyVisualizer_single.exe   (single file - portable)
echo ============================================
if exist dist\KeyVisualizer.zip explorer /select,"%cd%\dist\KeyVisualizer.zip"
pause
