# Датасеты и модели: источники и условия использования

Ниже только ресурсы, которые фактически использовались. Лицензии указаны по метаданным источников на 2026-11-08;
перед публичным или коммерческим использованием их нужно перепроверить.

## Датасеты

### PhiUSIIL Phishing URL Dataset
* Источник: UCI Machine Learning Repository, id 967 — https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset
* Авторы: A. Prasad, S. Chandra. *PhiUSIIL: A diverse security profile empowered phishing URL detection framework based on similarity index and incremental learning.* Computers & Security 136 (2024) 103545.
* Лицензия: **CC BY 4.0** (требуется указание авторства).
* Использование: обучение/валидация/тест классификатора URL. Из CSV берутся только столбцы `URL` и `label` (1 = легитимный, 0 = фишинг); готовые признаки датасета **не используются**.
* Загрузка: `python ml/url_classifier/download_data.py` (sha256 архива фиксируется в скрипте).
* Известная особенность: легитимные URL — почти всегда `https://www.<домен>` без пути. Поэтому схема и `www` исключены из признаков, а URL канонизируются.

### Web page phishing detection dataset (Hannousse & Yahiouche)
* Авторы: A. Hannousse, S. Yahiouche. *Towards benchmark datasets for machine learning based website phishing detection: An experimental study.* Engineering Applications of Artificial Intelligence (2021), DOI 10.1016/j.engappai.2021.104347 (цитирование по карточке датасета).
* Использованное зеркало: Hugging Face `pirocheto/phishing-url`, ревизия `1375d450d4540205ac11781b807249c9509739cd`.
* Лицензия: **CC BY 4.0**.
* Использование: часть обучающих данных и внешний тест (кросс-датасетный эксперимент). Используются только `url` и `status`.

### DeepFakeFace (DFF)
* Источник: Hugging Face `OpenRL/DeepFakeFace`, ревизия `eb2a54fbf2567790bd3dc61d09fdaade6bb6c31c`; статья: H. Song, S. Huang, Y. Dong, W.-W. Tu, *Robustness and Generalizability of Deepfake Detection: A Study with Diffusion Models*, arXiv:2309.02218.
* Лицензия: метаданные карточки — **OpenRAIL**; в тексте карточки дополнительно приведён блок `license: apache-2.0`. Указания противоречат друг другу, поэтому применяем более строгую трактовку (OpenRAIL, только исследование). Реальные изображения происходят из IMDB-WIKI — только для некоммерческих исследований.
* Использование: **только оценка** детектора (не обучение). Случайная выборка seed 7: 200 real (`wiki.zip`), 100 `insight.zip`, 100 `inpainting.zip`; скачиваются лишь выбранные файлы через HTTP Range (`ml/deepfake/fetch_dff_sample.py`). Изображения в репозиторий не включаются.

### Тестовая фотография
* `backend/tests/fixtures/lincoln_pd.jpg` — фотография А. Линкольна (1863, Alexander Gardner) из Wikimedia Commons, **public domain**. Используется в тесте реального inference.

## Модели

### Deep-Fake-Detector-v2-Model
* Источник: Hugging Face `prithivMLmods/Deep-Fake-Detector-v2-Model`, ревизия `3a99ae26f52c7ac7c3a53103b6cf3a8b617f7093`.
* Лицензия (метаданные карточки): **Apache-2.0**.
* Архитектура: ViT-B/16, база `google/vit-base-patch16-224-in21k`, 2 класса (`Realism`, `Deepfake`).
* Скачивание: `python ml/deepfake/download_weights.py` — берутся только `config.json`, `preprocessor_config.json`, `model.safetensors` (343 МБ), `README.md`; создаётся `qorgau_manifest.json` с sha256.
* Обучающие данные: в карточке описаны как «curated dataset of real and deepfake images» без точного источника; заявленные автором метрики (accuracy 0.9212) **не воспроизводились**. Наша оценка — `ml/reports/deepfake_eval.md`.

### OpenCV Haar cascade (frontal face)
* Файл `haarcascade_frontalface_default.xml`, поставляется в колесе `opencv-python-headless` 4.14 (Intel License Agreement / BSD-подобная; OpenCV 4.5+ — Apache-2.0). Ничего дополнительно не скачивается.

### Классификатор URL (собственный)
* Обучается скриптом `ml/url_classifier/train.py` на данных выше; артефакт `backend/models/url_classifier.joblib` (≈126 МБ) не хранится в репозитории.
* Версия, использованная в отчёте: `url-ra-20261108-da7020f5`.

### Claude (опционально)
* Модель по умолчанию `claude-opus-5-5` (переменная `LLM_MODEL`), вызывается только при наличии `ANTHROPIC_API_KEY` на сервере, через официальный SDK `anthropic`. Получает только обезличенные факты результата. Использование регулируется условиями Anthropic API.

### Google Safe Browsing (опционально)
* v4 Lookup API, включается переменной `GOOGLE_SAFE_BROWSING_API_KEY`. По условиям Google Lookup API предназначен для некоммерческого использования; при включении проверяемые URL отправляются в Google (раскрыто на экране «Приватность»).

## Детектор дипфейков (текущая модель)

* **buildborderless/CommunityForensics-DeepfakeDet-ViT**, ревизия `ac6ee457bea904a373065754107451793b56db00`, лицензия **MIT** (карточка модели). Архитектура ViT-S/16, один выход (вероятность подделки). Требует `transformers >= 5.4`.
* Загрузка: `python ml/deepfake/download_weights.py` (файлы: `config.json`, `preprocessor_config.json`, `model.safetensors`, лицензия).
* Обучающие данные: по описанию авторов — 2.7 млн изображений от 4803 генераторов (набор Community Forensics). Точный состав мы не проверяли.
* Прежняя модель `prithivMLmods/Deep-Fake-Detector-v2-Model` заменена: на нашей выборке она работала на уровне случайного угадывания (см. `docs/technical_report.md`, раздел 7).
