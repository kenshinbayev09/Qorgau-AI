# Требование → Реализация → Проверка

Статусы: ✅ реализовано и проверено автоматически · ◐ реализовано, проверено частично · ✗ не выполнено.

| # | Требование | Реализация | Проверка | Статус |
|---|---|---|---|---|
| 1 | Стек: Expo + TS, FastAPI, scikit-learn, PyTorch, SQLite | `mobile/`, `backend/`, `ml/` | `npx tsc`, `pytest`, сборка бандлов | ✅ |
| 2 | Ключи только на сервере, `.env.example` | `backend/app/config.py`, `backend/.env.example`; в `mobile/` секретов нет | ревью кода | ✅ |
| 3 | Основной сценарий без регистрации | нет аккаунтов; история локальна | — | ✅ |
| 4 | Инструкции запуска Android/iOS и требования сборки | `README.md` | запуск на устройствах **не выполнялся** | ◐ |
| 5 | Анализ структуры URL, длины, поддоменов, символов | `url_analysis/normalize.py`, `features.py`, `heuristics.py` | `test_url_parsing_and_rules.py` | ✅ |
| 6 | IP вместо домена (в т.ч. обфусцированный) | `normalize._parse_obfuscated_ipv4`, сигнал `ip_host` | `test_obfuscated_ipv4_is_decoded`, `test_ip_host_and_userinfo_and_params` | ✅ |
| 7 | Похожие домены и Unicode-подмены | `brand.py`, `text_utils.skeleton` | `test_typosquatting`, `test_cyrillic_homoglyph_of_apple`, `test_mixed_script_label_detected` | ✅ |
| 8 | Подозрительные слова и параметры | `heuristics.py` (`suspicious_keywords`, `email_in_query`, `open_redirect_param`) | `test_ip_host_and_userinfo_and_params` | ✅ |
| 9 | Цепочка редиректов при безопасном сетевом анализе | `net/safe_fetch.py`, `service.network_signals` | `test_ssrf.py`, `test_redirect_chain_signals` | ✅ |
| 10 | 4 категории, оценка с пометкой «оценка модели», признаки, советы, выполненные/недоступные проверки | `UrlCheckService.check`, экран `result/[id].tsx` | `test_url_service.py`, `test_api.py` | ✅ |
| 11 | HTTPS не доказательство безопасности | `no_tls` слабый сигнал, схема исключена из признаков ML | `test_https_alone_is_not_evidence_of_safety` | ✅ |
| 12 | Не открывать страницу автоматически | приложение не открывает ссылки (нет `Linking.openURL`); сервер не исполняет JS | ревью кода | ✅ |
| 13 | Загрузка фото/короткого видео | `media.tsx`, `/api/v1/media/upload` | `test_media.py` | ✅ |
| 14 | Прямая ссылка на медиа; соцсеть/HTML → предложить загрузку | `MediaService.analyse_url` | `test_social_page_link_needs_upload`, `test_media_link_to_html_page_asks_for_upload` | ✅ |
| 15 | Видео: ограниченное число кадров, оценки по кадрам, топ-кадры, версия модели, ограничения, «Недостаточно данных» | `deepfake/analysis.py`, `FrameStrip` | `test_video_without_faces_is_insufficient`, `test_face_image_runs_real_model` | ✅ |
| 16 | Реальная модель с лицензией и способом загрузки; «Модель не подключена» без весов | `ml/deepfake/download_weights.py` (Apache-2.0, pinned) | `test_model_not_connected`, `test_media_without_model_is_honest_503` | ✅ |
| 17 | Демо только в отдельном режиме с пометкой | `/api/v1/demo/media` (`demo: true`), переключатель в настройках, баннер «ДЕМО» | `test_demo_is_labelled` | ✅ |
| 18 | Не придумывать объяснения (глаза/губы/голос) | тексты UI и системный промпт LLM | ревью кода | ✅ |
| 19 | Агент: тип входа, выбор инструмента, вызов, ошибки, объяснение, состояния, действия, журнал | `agent/agent.py`, `assistant.tsx` | `test_agent.py` (20) | ✅ |
| 20 | Основные проверки без платного API; шаблоны по реальным результатам | `template_blocks`, `renderBlocks` | `test_url_input_selects_url_tool`, `flow.test.ts` | ✅ |
| 21 | Недоверенные данные не меняют инструкции | `sanitize_result`, фиксированный реестр инструментов | `test_prompt_injection_text_is_only_data`, `test_sanitize_drops_untrusted_free_text` | ✅ |
| 22 | QR: камера и изображение, показать домен, анализ до перехода | `scan.tsx` (`CameraView`, `scanFromURLAsync`), `previewDomain` | `flow.test.ts` (preview); камера — **не проверена на устройстве** | ◐ |
| 23 | История: поиск, фильтры, просмотр, удаление | `db/sqlite.ts`, `history.tsx` | `flow.test.ts` (на `MemoryHistoryRepo`); SQLite — **не проверено на устройстве** | ◐ |
| 24 | Обучающие карточки (3 шт.) | `learn/[id].tsx`, `i18n/*.learn` | `i18n.test.ts` | ✅ |
| 25 | Приватность: удаление истории, объяснение передачи данных | `settings.tsx`, `privacy.tsx` | ревью; UI **не проверен на устройстве** | ◐ |
| 26 | Не обещать фоновую защиту | тексты «О приложении» | ревью | ✅ |
| 27 | Неделя 1 — агент | раздел 1 отчёта | `test_agent.py` | ✅ |
| 28 | Неделя 8 — LR vs RF vs baseline, train/val/test, без дублей и пересечений доменов, P/R/F1/CM | `ml/url_classifier/train.py` | `ml/reports/url_classifier_report.md` | ✅ |
| 29 | Неделя 9 — локальный inference, агрегация, нет данных, скрипт оценки | `deepfake/*`, `ml/deepfake/evaluate.py` | `ml/reports/deepfake_eval.md` (ROC-AUC 0.489) | ✅ (качество модели низкое) |
| 30 | Дизайн: тёмная тема #0B1020/#151D30, акценты #2DD4BF/#60A5FA, светлая тема, радиусы 20–24, сетка 8, векторные иконки | `theme/theme.ts`, `components/*` | визуально **не проверено** на устройстве | ◐ |
| 31 | Статус цветом + текстом + иконкой; safe area, клавиатура, крупный шрифт, зоны нажатия ≥ 48 | `RiskBadge`, `Screen` (SafeAreaView, KeyboardAvoidingView), `touch = 48`, `maxFontSizeMultiplier` | ревью кода | ◐ |
| 32 | Нижняя навигация 4 вкладки; главная, экран результата по ТЗ | `(tabs)/_layout.tsx`, `index.tsx`, `result/[id].tsx` | сборка бандлов | ◐ |
| 33 | Реальные этапы обработки вместо фиктивных процентов | XHR `upload.onload` → «анализ»; `stages` с длительностями | ревью кода | ✅ |
| 34 | Пустые состояния, загрузка, ошибки сети, неверная ссылка, неподдерживаемый файл, нет лица, таймаут, модель недоступна | `EmptyState`, `ErrorBanner`, `errors.*`, `mediaReason.*` | `flow.test.ts` (маппинг ошибок) | ◐ |
| 35 | ru основной, kk и en, строки вне компонентов | `mobile/src/i18n/*` | `i18n.test.ts` (полнота ключей и плейсхолдеров) | ✅ (kk без вычитки носителем) |
| 36 | Сеть: только http/https, блок private/link-local/служебных IP, DNS и каждый редирект, rebinding, лимиты, без JS/форм | `safe_fetch.py` | `test_ssrf.py` (35 проверок) | ✅ |
| 37 | Файлы: фактический формат, размер, длительность, изоляция, лимиты ресурсов, удаление temp | `media.sniff`, `MediaService`, воркер-процесс | `test_media.py` | ✅ (RLIMIT только Linux/macOS) |
| 38 | Согласие перед первой отправкой медиа | модальное окно в `media.tsx` | ревью | ◐ |
| 39 | Не логировать секретные параметры | `redaction.py` | `test_secrets_never_logged` | ✅ |
| 40 | Тесты по списку п.7 ТЗ | `backend/tests/*`, `mobile/src/__tests__/*` | 123 + 12 тестов проходят | ✅ |
| 41 | Отдельная оценка ML с фактическими метриками | `ml/reports/*` | — | ✅ |
| 42 | Материалы для защиты | `docs/*` | — | ✅ |
| 43 | Дополнительно: проверка файла антивирусами (VirusTotal), по согласию пользователя | `backend/app/security/virustotal.py`, `POST /api/v1/file/scan`, `mobile/src/app/file-scan.tsx` | `backend/tests/test_virustotal.py` (мок сервиса, без сети и без ключа) | ◐ реальный ключ и работа на устройстве не проверены |
