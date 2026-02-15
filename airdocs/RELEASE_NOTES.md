# AirDocs - Релиз {VERSION}

## 📦 Установка для Windows

**Рекомендуется:** Скачайте `AirDocs_v{VERSION}_WIN.zip`

### Первый запуск:
1. **Распакуйте ZIP** в любую папку (например, `C:\AirDocs`)
2. **Запустите** `AirDocs_{VERSION}.exe`
3. **Мастер настройки**: добавьте контрагентов (отправителей/получателей)
4. **Готово!** Создавайте AWB в модуле "Бронирование"

> **Важно:** При первом запуске на чистой Windows может потребоваться установка [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe). Приложение покажет инструкцию при необходимости.

### Обновление существующей установки:
1. **Закройте** старую версию AirDocs
2. **Распакуйте** новый ZIP **в ТУ ЖЕ папку** (заменит exe)
3. **Данные сохранятся**: `data/awb_dispatcher.db`, логи, шаблоны
4. **Запустите** новую версию

> **Автообновление:** При запуске приложение автоматически проверяет GitHub на наличие новых версий.

---

## 📝 Изменения в версии {VERSION}

{CHANGELOG_SECTION}

---

## 📂 Структура данных (портативный режим)

- **База данных:** `data/awb_dispatcher.db`
- **Логи:** `data/logs/app.log`
- **Выходные файлы:** `data/output/` (AWB, Invoice, Act, UPD)
- **Шаблоны:** `data/templates/` (Word/Excel/PDF)

---

## 🆘 Поддержка

**При ошибках:**
- Отправьте `data/logs/app.log` разработчику
- Создайте Issue: [GitHub Issues](https://github.com/mashingaan/AirDocs/issues)

**Ошибка DLL при запуске:**
- Установите [VC++ Redistributable x64](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- См. `README_WIN.txt` в архиве для подробностей

**Документация:**
- [Полный CHANGELOG](https://github.com/mashingaan/AirDocs/blob/main/airdocs/CHANGELOG.md)
- [Система обновлений](https://github.com/mashingaan/AirDocs/blob/main/airdocs/docs/UPDATE_SYSTEM.md)

---

**Версия:** {VERSION} | **Дата:** {DATE} | **Репозиторий:** [mashingaan/AirDocs](https://github.com/mashingaan/AirDocs)

