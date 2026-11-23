# Сравнение детекторов дипфейков

Выборка: DeepFakeFace seed 7 (200 real + 200 fake). Дата: 2026-11-23T16:11:37.050672+00:00.

| модель | лицензия | ROC-AUC (полное фото) | ROC-AUC (лицо) | n лицо | среднее real / fake |
|---|---|---|---|---|---|
| prithivMLmods/Deep-Fake-Detector-v2-Model | apache-2.0 | 0.505 | 0.489 | 283 | 0.73 / 0.73 |
| dima806/deepfake_vs_real_image_detection | apache-2.0 | 0.489 | 0.580 | 283 | 0.05 / 0.05 |
| buildborderless/CommunityForensics-DeepfakeDet-ViT | mit | 0.862 | 0.824 | 283 | 0.00 / 0.41 |
| prithivMLmods/AI-vs-Deepfake-vs-Real-Siglip2 | apache-2.0 | 0.421 | 0.314 | 283 | 0.95 / 0.93 |
