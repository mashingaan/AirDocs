@echo off
setlocal

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
if exist "build" rmdir /s /q "build"
if exist "dist\AirDocs.exe" del /q "dist\AirDocs.exe"
if exist "dist\AirDocs_%VERSION%.exe" del /q "dist\AirDocs_%VERSION%.exe"
if exist "dist\AirDocs_v%VERSION%_WIN.zip" del /q "dist\AirDocs_v%VERSION%_WIN.zip"
if exist "dist\README_WIN.txt" del /q "dist\README_WIN.txt"

REM === 3. Генерация version_info.txt для PyInstaller ===
echo Generating version metadata...
if exist "version_info.txt" del /q "version_info.txt"
python scripts\generate_version_info.py
if errorlevel 1 (
    echo ERROR: Version info generation failed^!
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
python -m PyInstaller AirDocs.spec --noconfirm

if errorlevel 1 (
    echo ERROR: PyInstaller failed^!
    pause
    exit /b 1
)

REM === 4.5. Rename EXE to versioned name ===
echo.
echo Renaming EXE to AirDocs_%VERSION%.exe...
if not exist "dist\AirDocs.exe" (
    echo ERROR: dist\AirDocs.exe not found after PyInstaller^!
    pause
    exit /b 1
)
move "dist\AirDocs.exe" "dist\AirDocs_%VERSION%.exe"
if errorlevel 1 (
    echo ERROR: Failed to rename EXE^!
    pause
    exit /b 1
)
echo EXE renamed successfully.

REM === 4.6. Copy README_WIN.txt to dist ===
echo.
echo Copying README_WIN.txt...
if not exist "README_WIN.txt" (
    echo ERROR: README_WIN.txt not found in project root^!
    pause
    exit /b 1
)
copy /y "README_WIN.txt" "dist\README_WIN.txt" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy README_WIN.txt^!
    pause
    exit /b 1
)
echo README_WIN.txt copied to dist.

REM === 5. Create ZIP archive ===
echo.
echo Creating release archive...
if not exist "dist\AirDocs_%VERSION%.exe" (
    echo ERROR: Versioned EXE not found^!
    pause
    exit /b 1
)
if not exist "dist\README_WIN.txt" (
    echo ERROR: dist\README_WIN.txt not found^!
    pause
    exit /b 1
)

powershell -Command "Compress-Archive -Path 'dist\AirDocs_%VERSION%.exe','dist\README_WIN.txt' -DestinationPath 'dist\AirDocs_v%VERSION%_WIN.zip' -Force"

if errorlevel 1 (
    echo ERROR: ZIP creation failed^!
    pause
    exit /b 1
)
echo ZIP created: dist\AirDocs_v%VERSION%_WIN.zip

REM === 6. Git tag и push (опционально) ===
echo.
set /p CREATE_TAG="Create git tag v%VERSION% and push? (y/n): "
if /i "%CREATE_TAG%"=="y" (
    echo Creating git tag...
    git tag -a "v%VERSION%" -m "Release v%VERSION%"
    git push origin "v%VERSION%"
    echo Tag v%VERSION% pushed to GitHub
)

REM === 6.5. Извлечение версионных заметок из CHANGELOG.md ===
echo.
echo Extracting release notes from CHANGELOG.md...
powershell -Command "$version = '%VERSION%'; $changelog = Get-Content 'CHANGELOG.md' -Raw -Encoding UTF8; if ($changelog -match '(?s)## \[' + [regex]::Escape($version) + '\].*?\n(.*?)(?=\n## \[|\z)') { $notes = $matches[1].Trim(); if ($notes) { $notes } else { 'См. CHANGELOG.md для деталей' } } else { 'Релиз версии ' + $version }" > "dist\release_notes_temp.txt"

if not exist "dist\release_notes_temp.txt" (
    echo WARNING: Failed to extract changelog notes, using fallback
    echo См. CHANGELOG.md для полного списка изменений > "dist\release_notes_temp.txt"
)

REM === 7. Создание GitHub Release (требует GitHub CLI) ===
echo.
set /p CREATE_RELEASE="Create GitHub Release? (requires gh CLI) (y/n): "
if /i "%CREATE_RELEASE%"=="y" (
    echo Creating GitHub Release...
    
    REM Создание финального release body из шаблона
    powershell -Command "$version = '%VERSION%'; $date = Get-Date -Format 'dd.MM.yyyy'; $template = Get-Content 'RELEASE_NOTES.md' -Raw -Encoding UTF8; $changelog = Get-Content 'dist\release_notes_temp.txt' -Raw -Encoding UTF8; $body = $template -replace '\{VERSION\}', $version -replace '\{DATE\}', $date -replace '\{CHANGELOG_SECTION\}', $changelog; Set-Content 'dist\release_body.md' -Value $body -Encoding UTF8"
    
    gh release create "v%VERSION%" ^
        "dist\AirDocs_v%VERSION%_WIN.zip#AirDocs_v%VERSION%_WIN.zip" ^
        "dist\AirDocs_%VERSION%.exe#AirDocs_%VERSION%.exe" ^
        --title "AirDocs v%VERSION%" ^
        --notes-file dist\release_body.md ^
        --repo mashingaan/AirDocs
    
    if errorlevel 1 (
        echo WARNING: GitHub Release creation failed. Install GitHub CLI: https://cli.github.com/
    ) else (
        echo GitHub Release created successfully^!
        echo Release notes: dist\release_body.md
    )
)


REM === Cleanup ===
if exist "dist\release_notes_temp.txt" del /q "dist\release_notes_temp.txt"
if exist "dist\release_body.md" del /q "dist\release_body.md"

echo.
echo ========================================
echo Build Complete^!
echo ========================================
echo Version: %VERSION%
echo Standalone EXE: dist\AirDocs_%VERSION%.exe
echo Archive: dist\AirDocs_v%VERSION%_WIN.zip
echo README: dist\README_WIN.txt
echo.
echo ИНСТРУКЦИЯ:
echo - Отправьте клиенту: dist\AirDocs_v%VERSION%_WIN.zip
echo - Внутри ZIP: AirDocs_%VERSION%.exe + README_WIN.txt
echo - Клиент: распаковать ^> запустить EXE ^> data/ создастся
echo.
pause

