@echo off
cd /d "%~dp0"

echo ============================================
echo  Build Key Visualizer  (full + Lite, folder + single)
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

REM ---- App icon: if icon.png exists, use it for the exe and the window (PyInstaller needs Pillow) ----
set ICON_ARGS=
if exist icon.png (
    pip show pillow >nul 2>&1
    if errorlevel 1 pip install pillow
    set ICON_ARGS=--icon icon.png --add-data "icon.png;."
    echo Using icon.png
) else (
    echo [INFO] icon.png not found - using default icon.
)
echo.

echo [1/4] Folder build (antivirus-friendly, recommended)...
python -m PyInstaller --onedir --noconsole --name KeyVisualizer --clean --noconfirm %ICON_ARGS% key_visualizer.py
if errorlevel 1 (
    echo [ERROR] Folder build failed. Copy the error message above to Claude.
    pause
    exit /b 1
)

echo.
echo [2/4] Single-file build (portable, more AV false positives)...
python -m PyInstaller --onefile --noconsole --name KeyVisualizer_single --noconfirm %ICON_ARGS% key_visualizer.py
if errorlevel 1 (
    echo [ERROR] Single-file build failed.
    pause
    exit /b 1
)

echo.
echo [3/4] Lite folder build (no recording)...
python -m PyInstaller --onedir --noconsole --name KeyVisualizer_Lite --noconfirm %ICON_ARGS% key_visualizer_lite.py
if errorlevel 1 (
    echo [ERROR] Lite build failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Lite single-file build (no recording, portable)...
python -m PyInstaller --onefile --noconsole --name KeyVisualizer_Lite_single --noconfirm %ICON_ARGS% key_visualizer_lite.py
if errorlevel 1 (
    echo [ERROR] Lite single-file build failed.
    pause
    exit /b 1
)

if exist config.json copy /y config.json dist\KeyVisualizer\config.json >nul
if exist config.json copy /y config.json dist\KeyVisualizer_Lite\config.json >nul

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
if exist dist\KeyVisualizer_Lite.zip del /q dist\KeyVisualizer_Lite.zip
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\KeyVisualizer_Lite' -DestinationPath 'dist\KeyVisualizer_Lite.zip' -CompressionLevel Optimal -Force"
if errorlevel 1 (
    echo [WARN] Lite zip failed. Compress the dist\KeyVisualizer_Lite folder manually.
) else (
    echo Zip created: dist\KeyVisualizer_Lite.zip
)

echo.
echo ============================================
echo  Done. Upload these four:
echo    dist\KeyVisualizer.zip          (folder build - recommended)
echo    dist\KeyVisualizer_single.exe   (single file - portable)
echo    dist\KeyVisualizer_Lite.zip          (no recording - folder)
echo    dist\KeyVisualizer_Lite_single.exe   (no recording - single file)
echo ============================================
if exist dist\KeyVisualizer.zip explorer /select,"%cd%\dist\KeyVisualizer.zip"
pause
