# Система обновлений

## Архитектура

Система обновлений работает полностью на Python и использует отложенную установку при следующем запуске:

1. ZIP скачивается в `data/updates/`.
2. После загрузки выполняется SHA256-проверка (если хеш указан).
3. Архив извлекается в `data/updates/extracted_v{version}/` с прогрессом.
4. Создается `.pending_update` с путем к извлеченным файлам и метаданными.
5. При следующем запуске `main.py` применяет обновление до инициализации UI.
6. При ошибке выполняется rollback через `app_dir_old/`.

## Диаграмма последовательности

```mermaid
sequenceDiagram
    participant User
    participant App
    participant GitHub
    participant UpdateDialog
    participant Updater
    participant FileSystem

    Note over App: Startup
    App->>FileSystem: Check .pending_update
    alt Pending update exists
        App->>Updater: apply_pending_update()
        Updater->>FileSystem: Rename app_dir → app_dir_old
        Updater->>FileSystem: Copy extracted_path → app_dir
        Updater->>FileSystem: Verify installation
        alt Success
            Updater->>FileSystem: Delete app_dir_old
            Updater->>User: Show "Update installed"
        else Failure
            Updater->>FileSystem: Rollback (app_dir_old → app_dir)
            Updater->>User: Show error
        end
        Updater->>FileSystem: Delete .pending_update
    end

    Note over App: Normal startup
    App->>GitHub: Check for updates
    GitHub-->>App: Latest release info
    
    alt Update available
        App->>UpdateDialog: Show update dialog
        User->>UpdateDialog: Click "Install now"
        
        UpdateDialog->>Updater: download_update()
        Updater->>GitHub: Download ZIP
        GitHub-->>Updater: ZIP file
        Updater-->>UpdateDialog: Progress updates
        
        UpdateDialog->>Updater: verify_update()
        Updater->>FileSystem: Check SHA256
        
        UpdateDialog->>Updater: extract_update_with_progress()
        Updater->>FileSystem: Extract to data/updates/extracted_v{version}/
        Updater-->>UpdateDialog: Progress updates
        
        UpdateDialog->>FileSystem: Create .pending_update
        UpdateDialog->>User: "Restart to install?"
        
        alt User clicks Yes
            User->>App: Restart
            Note over App: apply_pending_update() runs on next startup
        else User clicks No
            Note over App: Update will install on next startup
        end
    end
```

## Формат `.pending_update` JSON

```json
{
  "version": "0.1.5",
  "extracted_path": "C:/Users/User/Desktop/AWB/airdocs/data/updates/extracted_v0.1.5",
  "url": "https://github.com/mashingaan/AirDocs/releases/download/v0.1.5/AirDocs_v0.1.5.zip",
  "sha256": "abc123...",
  "size": 52428800,
  "release_date": "2026-02-05T10:30:00Z",
  "release_notes": "## Changes\n- Fixed bug X\n- Added feature Y",
  "channel": "latest",
  "download_timestamp": "2026-02-05T12:00:00Z"
}
```

## Обработка ошибок и rollback

- При ошибке установки выполняется откат: `app_dir_old` переименовывается обратно в `app_dir`.
- При критической ошибке отката пользователь получает сообщение с путями для ручного восстановления.
- Все шаги установки логируются в `data/logs/updater.log`.

## Безопасность

- Проверка SHA256 защищает от поврежденных или подмененных архивов.
- Если SHA256 не задан, проверка пропускается, но загрузка все равно выполняется.
