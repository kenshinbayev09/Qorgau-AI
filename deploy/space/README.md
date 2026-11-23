---
title: Qorgau AI API
emoji: 🛡️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Backend для проверки фишинга и дипфейков
---

# Qorgau AI — API

Сервер для мобильного приложения Qorgau AI (учебный проект QAIRU AI Fundamentals).

* `GET /api/v1/health` — состояние моделей и сервисов
* `POST /api/v1/url/check` — проверка ссылки
* `POST /api/v1/media/upload` — проверка фото/видео на признаки дипфейка
* `POST /api/v1/agent/run` — AI-помощник

Ключи внешних сервисов задаются в Settings Space (Secrets), а не в коде.
