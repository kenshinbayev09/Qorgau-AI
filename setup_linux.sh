#!/usr/bin/env bash
# Установка проекта на Linux. Запускать один раз: bash setup_linux.sh
set -e
cd "$(dirname "$0")"

echo "== 1/3 Проверка Python 3.12"
PY=$(command -v python3.12 || true)
if [ -z "$PY" ]; then
  echo "Не найден Python 3.12. Установите его командой:"
  echo "  sudo apt install python3.12 python3.12-venv"
  exit 1
fi

echo "== 2/3 Серверные библиотеки (несколько минут)"
"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

echo "== 3/3 Библиотеки приложения"
if ! command -v npm >/dev/null; then
  echo "Не найден Node.js (нужна версия 22.13 или новее). Установите:"
  echo "  sudo apt install nodejs npm"
  exit 1
fi
(cd mobile && npm install)

echo ""
echo "ГОТОВО. Дальше запустите: bash start_linux.sh"
