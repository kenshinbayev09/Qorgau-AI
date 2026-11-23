#!/usr/bin/env bash
# Запуск проекта на Linux: bash start_linux.sh
cd "$(dirname "$0")"

echo "== Сервер (backend) запускается в фоне"
(cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../backend_server_log.txt 2>&1 &)
sleep 6
if curl -s http://127.0.0.1:8000/api/v1/health >/dev/null; then
  echo "Сервер работает. Проверка: http://localhost:8000/docs"
else
  echo "Сервер не запустился. Посмотрите файл backend_server_log.txt"
fi

echo "== Сайт запускается в фоне: http://localhost:8090"
(cd mobile && ../.venv/bin/python serve_web.py > ../web_server_log.txt 2>&1 &)

echo "== Приложение для телефона (Expo)"
if [ -z "$EXPO_TOKEN" ]; then
  echo "Вставьте токен Expo (новый, с expo.dev) и нажмите Enter."
  echo "Символы при вставке не видны, это нормально."
  read -r -s EXPO_TOKEN
  echo ""
  export EXPO_TOKEN
fi
cd mobile && npx expo start --lan --clear
