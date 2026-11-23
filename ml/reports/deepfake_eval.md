# Deepfake detector evaluation

Generated 2026-11-08T11:25:26.956724+00:00 by `ml/deepfake/evaluate.py`.

| metric | value |
|---|---|
| mode | api_pipeline_face_crop |
| n_images | 400 |
| n_scored | 283 |
| abstained_no_face | {'real': 53, 'fake': 64} |
| threshold | 0.5 |
| precision_fake | 0.4663 |
| recall_fake | 0.6103 |
| f1_fake | 0.5287 |
| roc_auc | 0.4892 |
| confusion_matrix | {'tn': 52, 'fp': 95, 'fn': 53, 'tp': 83} |
| seconds | 119.0000 |
