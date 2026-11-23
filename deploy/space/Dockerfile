# Контейнер для бесплатного хостинга (Hugging Face Spaces, SDK = Docker).
# Этот файл копируется в корень Space-репозитория вместе с backend/ (см. deploy/make_space.py).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OpenCV (headless) нужны системные библиотеки GL/GLib
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости отдельным слоем, чтобы пересборка не качала их заново
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Код сервера и файл модели URL-классификатора (обучен локально)
COPY backend backend

# Веса детектора дипфейков скачиваются при сборке (ревизия зафиксирована в скрипте)
COPY ml/deepfake/download_weights.py ml/deepfake/download_weights.py
RUN python ml/deepfake/download_weights.py

# Работаем не от root
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

ENV URL_MODEL_PATH=/app/backend/models/url_classifier.joblib \
    DEEPFAKE_MODEL_DIR=/app/ml/deepfake/weights/community-forensics-vit \
    MEDIA_ISOLATION=process \
    TORCH_THREADS=2 \
    NETWORK_CHECKS_ENABLED=true \
    MAX_UPLOAD_MB=50 \
    MAX_VIDEO_SECONDS=60

WORKDIR /app/backend

# Hugging Face Spaces ожидает порт 7860
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
