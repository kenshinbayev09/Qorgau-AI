# Qorgau AI

**Авторы:** Кеншинбаев Нұртуған, Қалиаскер Мирас
**Курс:** QAIRU AI Fundamentals, Final Project 2026

Мобильное приложение (iOS / Android) для проверки **фишинговых ссылок** и **признаков дипфейков** на изображениях и видео.
Учебный проект курса **QAIRU AI Fundamentals**. Работает без регистрации; проверяет только то, что пользователь передал сам
(никакой фоновой защиты и блокировки сайтов).

| Каталог | Что внутри |
|---|---|
| `mobile/` | React Native + Expo SDK 58 + TypeScript (Expo Router, SQLite-история, камера/QR, ru/kk/en) |
| `backend/` | Python 3.12 + FastAPI: анализ URL, SSRF-безопасный сетевой модуль, детектор дипфейков (PyTorch), агент |
| `ml/` | обучение и оценка классификатора URL (scikit-learn), загрузка весов и оценка детектора дипфейков |
| `docs/` | технический отчёт, таблица требований, источники и лицензии, сценарий демо, презентация, декларации |

## Архитектура

```
 ┌──────────────── mobile (Expo) ────────────────┐            ┌──────────────────────── backend (FastAPI) ────────────────────────┐
 │ Главная · AI-помощник · История · Настройки   │  HTTPS     │ /api/v1/url/check ── normalize ─ brand/homoglyph ─ heuristics     │
 │ Результат · Медиа · QR-сканер · Обучение      │ ─────────▶ │                    └─ RandomForest (joblib) ─┐                     │
 │                                               │            │                    └─ SafeFetcher (DNS-pinning, SSRF-guard) ──┤→ score │
 │ SQLite: история и настройки (только на       │            │ /api/v1/media/*  ── magic-bytes ─ temp file ─ worker process:      │
 │ устройстве) · QR распознаётся на устройстве   │ ◀───────── │                    frames → Haar face → ViT (PyTorch) → median     │
 └───────────────────────────────────────────────┘   JSON     │ /api/v1/agent/run ─ QorgauAgent (states, tools, trace, templates) │
                                                              │                    └─ optional Claude paraphrase (server key)    │
                                                              └───────────────────────────────────────────────────────────────────┘
```

Подробно — [docs/technical_report.md](docs/technical_report.md).

## Что работает и что проверено (на 2026-11-08)

| Компонент | Статус | Как проверено |
|---|---|---|
| Анализ URL (структура, IP, поддомены, гомоглифы/Unicode, тайпсквоттинг, параметры) | работает | `backend/tests/test_url_parsing_and_rules.py` |
| Классификатор URL (RF vs LR vs baseline) | обучен на реальных данных | `ml/reports/url_classifier_report.md` (test F1 RF = 0.809) |
| SSRF-безопасная проверка редиректов | работает | `backend/tests/test_ssrf.py` (локальный сервер, DNS-rebinding, лимиты) |
| Детектор дипфейков (ViT, локальный inference) | работает, **качество низкое на внешних данных** | `backend/tests/test_media.py`; `ml/reports/deepfake_eval.md` (ROC-AUC ≈ 0.49 на DeepFakeFace) |
| Агент (состояния, выбор инструмента, ошибки, трассировка) | работает | `backend/tests/test_agent.py` |
| API end-to-end | работает | `backend/tests/test_api.py` |
| Мобильное приложение | компилируется, бандлы iOS/Android собираются, unit-тесты проходят | `npx tsc --noEmit`, `npx jest`, `npx expo export`, `npx expo-doctor` |
| Запуск на реальном iOS/Android устройстве или эмуляторе | **не выполнялся** | — |
| LLM-объяснения (Claude) и Google Safe Browsing | реализованы, **не проверены с реальными ключами** | без ключей корректно отключаются (тесты) |

## Требования

* **Backend/ML:** Python **3.12** (3.15 пока не подходит — часть колёс не собирается), ~2 ГБ RAM для детектора, ~1.5 ГБ диска (веса 343 МБ + PyTorch).
* **Mobile:** Node.js **22.13+** (проверено на 22.23), npm 10+. Требования Expo SDK 58 (по [docs.expo.dev/versions](https://docs.expo.dev/versions/latest/)):
  * **Android 7+** на устройстве. Сборка: Expo Go для SDK 58 *или* Android Studio с Android SDK **compileSdk 37** / targetSdk 36 и **JDK 17** для `npx expo run:android`.
  * **iOS 16.4+** на устройстве. Сборка: Expo Go для SDK 58 *или* macOS + **Xcode 26.4+** для `npx expo run:ios`. Без Mac — облачная сборка `npx eas-cli@latest build -p ios` (нужен аккаунт Apple Developer).

## Быстрый старт

### 1. Backend

```bash
cd backend
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements-dev.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

(Windows: `.venv\Scripts\pip ...`.) Затем из корня репозитория скачайте данные и модели:

```bash
python ml/url_classifier/download_data.py
```

```bash
python ml/url_classifier/train.py
```

```bash
python ml/deepfake/download_weights.py
```

Запуск API (из `backend/`, слушать все интерфейсы, чтобы телефон в той же Wi-Fi сети мог подключиться):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Проверка: `http://<IP-компьютера>:8000/api/v1/health`. Без шага `download_weights.py` анализ медиа честно отвечает «Модель не подключена» (HTTP 503).

### 2. Mobile

```bash
cd mobile
npm install
```

Укажите адрес backend (IP компьютера в локальной сети) — в `mobile/.env` (`EXPO_PUBLIC_API_URL=http://192.168.1.10:8000`) или позже в приложении: **Настройки → Сервер**.

```bash
npx expo start
```

* **Android:** отсканируйте QR из терминала в Expo Go, или нажмите `a` для эмулятора (адрес по умолчанию `http://10.0.2.2:8000`).
* **iOS:** отсканируйте QR камерой iPhone (откроется Expo Go), или `i` для симулятора на macOS (по умолчанию `http://localhost:8000`).
* Нативная сборка: `npx expo run:android` / `npx expo run:ios`.

> HTTP без TLS к локальному серверу работает в Expo Go. Для production-сборок разверните backend за **HTTPS**: Android по умолчанию запрещает cleartext-трафик, iOS ATS — тоже.

### 3. Тесты и оценка

```bash
cd backend && python -m pytest
```

```bash
cd mobile && npx tsc --noEmit && npx jest
```

```bash
python ml/deepfake/fetch_dff_sample.py --per-class 200 && python ml/deepfake/evaluate.py --data-dir ml/data/deepfake_eval
```

## Документы для защиты

* [Технический отчёт (3 AI-темы)](docs/technical_report.md)
* [Требование → Реализация → Проверка](docs/requirements_traceability.md)
* [Датасеты, модели, лицензии](docs/models_and_datasets.md)
* [Сценарий демонстрации](docs/demo_script.md) · [Структура презентации](docs/presentation_outline.md)
* [AI Usage Declaration](docs/ai_usage_declaration.md) · [Team Contribution Statement (шаблон)](docs/team_contribution_template.md)
