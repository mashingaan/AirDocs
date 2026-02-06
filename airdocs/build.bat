@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
echo ========================================
echo AirDocs Build Script v2.0
echo ========================================
echo.

REM === 1. Читаем версию из core/version.py ===
for /f "tokens=2 delims==" %%a in ('findstr /C:"VERSION = " core\version.py') do (
    set VERSION_LINE=%%a
)
set VERSION=%VERSION_LINE:"=%
set VERSION=%VERSION: =%
echo Current version: %VERSION%
echo.

REM === 2. Очистка предыдущих сборок ===
echo Cleaning previous builds...
if exist "dist\AirDocs" rmdir /s /q "dist\AirDocs"
if exist "build" rmdir /s /q "build"
if exist "dist\AirDocs_%VERSION%.zip" del /q "dist\AirDocs_%VERSION%.zip"

REM === 3. Генерация version_info.txt для PyInstaller ===
echo Generating version metadata...
if exist "version_info.txt" del /q "version_info.txt"
python scripts\generate_version_info.py
if errorlevel 1 (
    echo ERROR: Version info generation failed!
    pause
    exit /b 1
)

if not exist "version_info.txt" (
    echo ERROR: version_info.txt was not created!
    echo Check if core/version.py exists and contains VERSION and __version_info__
    pause
    exit /b 1
)

echo Version info generated successfully.

REM === 4. Сборка с PyInstaller ===
echo.
echo Building with PyInstaller...
pyinstaller AirDocs.spec --noconfirm

if errorlevel 1 (
    echo ERROR: PyInstaller failed!
    pause
    exit /b 1
)

REM === 5. Создание ZIP-архива ===
echo.
echo Creating release archive...
powershell -Command "Compress-Archive -Path 'dist\AirDocs\*' -DestinationPath 'dist\AirDocs_%VERSION%.zip' -Force"

REM === 6. Git tag и push (опционально) ===
echo.
set /p CREATE_TAG="Create git tag v%VERSION% and push? (y/n): "
if /i "%CREATE_TAG%"=="y" (
    echo Creating git tag...
    git tag -a "v%VERSION%" -m "Release v%VERSION%"
    git push origin "v%VERSION%"
    echo Tag v%VERSION% pushed to GitHub
)

REM === 7. Создание GitHub Release (требует GitHub CLI) ===
echo.
set /p CREATE_RELEASE="Create GitHub Release? (requires gh CLI) (y/n): "
if /i "%CREATE_RELEASE%"=="y" (
    echo Creating GitHub Release...
    gh release create "v%VERSION%" ^
        "dist\AirDocs_%VERSION%.zip#AirDocs_%VERSION%.zip" ^
        "dist\AirDocs\AirDocs_%VERSION%.exe#AirDocs_%VERSION%.exe" ^
        --title "AirDocs v%VERSION%" ^
        --notes-file CHANGELOG.md ^
        --repo mashingaan/AirDocs
    
    if errorlevel 1 (
        echo WARNING: GitHub Release creation failed. Install GitHub CLI: https://cli.github.com/
    ) else (
        echo GitHub Release created successfully!
    )
)

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo Version: %VERSION%
echo Output: dist\AirDocs\
echo Archive: dist\AirDocs_%VERSION%.zip
echo.
pause
