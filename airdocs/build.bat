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
if exist "dist\AirDocs" rmdir /s /q "dist\AirDocs"
if exist "build" rmdir /s /q "build"
if exist "dist\AirDocs_v%VERSION%_WIN.zip" del /q "dist\AirDocs_v%VERSION%_WIN.zip"

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

REM === 4.2. Создание структуры data/ для портативного режима ===
echo.
echo Creating portable data structure...
if not exist "dist\AirDocs\data" mkdir "dist\AirDocs\data"
if not exist "dist\AirDocs\data\logs" mkdir "dist\AirDocs\data\logs"
if not exist "dist\AirDocs\data\output" mkdir "dist\AirDocs\data\output"
if not exist "dist\AirDocs\data\backups" mkdir "dist\AirDocs\data\backups"
if not exist "dist\AirDocs\data\templates" mkdir "dist\AirDocs\data\templates"
echo Data directories created.

REM === 4.2.1. Placeholders for empty data folders in ZIP ===
echo Adding placeholders for empty data folders...
type nul > "dist\AirDocs\data\logs\.keep"
type nul > "dist\AirDocs\data\output\.keep"
type nul > "dist\AirDocs\data\backups\.keep"
type nul > "dist\AirDocs\data\templates\.keep"
echo Placeholders created.

REM === 4.3. Создание README_WIN.txt ===
echo Creating README_WIN.txt...
(
echo ========================================
echo AirDocs v%VERSION% - Инструкция
echo ========================================
echo.
echo ЧТО ЭТО:
echo --------
echo AirDocs - система управления AWB и документами.
echo Полностью портативная: все данные в папке data/.
echo.
echo ПЕРВЫЙ ЗАПУСК:
echo --------------
echo 1. Распакуйте ZIP в любую папку ^(например, C:\AirDocs^)
echo 2. Дважды кликните AirDocs_%VERSION%.exe
echo 3. Мастер настройки: добавьте контрагентов
echo 4. Готово! Создавайте AWB в модуле "Бронирование"
echo.
echo ОБНОВЛЕНИЕ:
echo -----------
echo - Автоматическое: при запуске проверяется GitHub
echo - Ручное: распакуйте новый ZIP в ТУ ЖЕ папку
echo   ^(data/awb_dispatcher.db сохранится!^)
echo.
echo ДАННЫЕ:
echo -------
echo - База данных: data/awb_dispatcher.db
echo - Логи: data/logs/app.log
echo - Выходные файлы: data/output/
echo - Шаблоны: data/templates/
echo.
echo ПОДДЕРЖКА:
echo ----------
echo При ошибках отправьте data/logs/app.log
echo GitHub: https://github.com/mashingaan/AirDocs
echo.
echo ========================================
echo Версия: %VERSION%
echo Дата: 14.02.2026
echo ========================================
) > "dist\AirDocs\README_WIN.txt"
echo README_WIN.txt created.

REM === 4.1. Копирование config рядом с EXE (runtime ожидает app_dir\config\settings.yaml) ===
echo.
echo Copying config...
if not exist "dist\\AirDocs\\config" mkdir "dist\\AirDocs\\config"
xcopy "config" "dist\\AirDocs\\config\\" /E /I /Y >nul

REM === 5. Create ZIP archive ===
echo.
echo Creating release archive...
powershell -Command "Compress-Archive -Path 'dist\AirDocs\*' -DestinationPath 'dist\AirDocs_v%VERSION%_WIN.zip' -Force"

REM === 5.0. Cleanup placeholder files after ZIP creation ===
if exist "dist\AirDocs\data\logs\.keep" del /q "dist\AirDocs\data\logs\.keep"
if exist "dist\AirDocs\data\output\.keep" del /q "dist\AirDocs\data\output\.keep"
if exist "dist\AirDocs\data\backups\.keep" del /q "dist\AirDocs\data\backups\.keep"
if exist "dist\AirDocs\data\templates\.keep" del /q "dist\AirDocs\data\templates\.keep"

REM === 5.1. Создание standalone копии EXE ===
echo.
echo Creating standalone EXE copy...
copy "dist\AirDocs\AirDocs_%VERSION%.exe" "dist\AirDocs_%VERSION%.exe" >nul
if errorlevel 1 (
    echo WARNING: Failed to create standalone EXE copy
) else (
    echo Standalone EXE: dist\AirDocs_%VERSION%.exe
)

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
echo Output: dist\AirDocs\
echo Archive: dist\AirDocs_v%VERSION%_WIN.zip
echo.
pause

