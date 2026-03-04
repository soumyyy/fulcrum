# Fulcrum `/models` Response Reference

This note explains every field currently returned by the backend `GET /models` endpoint and how to interpret it in the frontend.

## Top-level response shape

The endpoint returns a JSON object with these top-level fields:

- `status`
- `production_model`
- `model_count`
- `models`

## Top-level variables

### `status`

- Type: `string`
- Current typical value: `ok`
- Meaning: whether the model registry call succeeded at the API layer

If this is not `ok`, the frontend should treat the response as a failed model-catalog load.

### `production_model`

- Type: `string`
- Example: `logistic_regression`
- Meaning: the model currently selected as the live production/default scoring model

This is the model used by the scoring API unless the backend selection rule changes.

### `model_count`

- Type: `number`
- Example: `3`
- Meaning: how many trained models are currently present in the registry output

As you add more models in the future, this value should increase automatically.

### `models`

- Type: `array`
- Meaning: a list of model records, one per trained model

Each item in this array contains the full metadata and metrics for a single trained model.

---

## Per-model object shape

Each item in `models[]` currently contains:

- `model_name`
- `is_production`
- `artifact_paths`
- `leaderboard_metrics`
- `threshold_config`
- `feature_config`
- `validation_metrics`
- `test_metrics`

---

## Per-model variables

### `model_name`

- Type: `string`
- Examples:
  - `logistic_regression`
  - `random_forest`
  - `hist_gradient_boosting`
- Meaning: the internal identifier for the trained model

This is the primary name you should show in the UI and use for model comparison.

### `is_production`

- Type: `boolean`
- Meaning: whether this model is the active production/default model

`true` means:
- this model is the one the scoring API uses by default
- this model matched the current production-selection logic after training

`false` means:
- this model is still trained and benchmarked
- it remains available for comparison
- it is not the default scoring model

---

## `artifact_paths`

This object tells you where the generated files for this model live.

Current fields:

- `model`
- `threshold`
- `features`

### `artifact_paths.model`

- Type: `string`
- Meaning: path to the serialized trained model artifact (`.joblib`)

This is the actual saved model bundle used for inference.

### `artifact_paths.threshold`

- Type: `string`
- Meaning: path to the saved threshold configuration JSON

This stores the calibrated classification threshold chosen on validation.

### `artifact_paths.features`

- Type: `string`
- Meaning: path to the saved feature configuration JSON

This stores the feature schema used when the model was trained.

---

## `leaderboard_metrics`

This is the flattened summary row from the model leaderboard CSV.

Current fields:

- `model_name`
- `threshold`
- `validation_pr_auc`
- `validation_roc_auc`
- `validation_brier_score`
- `validation_precision`
- `validation_recall`
- `validation_f1`
- `test_pr_auc`
- `test_roc_auc`
- `test_brier_score`
- `test_precision`
- `test_recall`
- `test_f1`

These are ideal for the first row of model comparison in the UI.

### `leaderboard_metrics.threshold`

- Type: `number`
- Meaning: the threshold used to convert probability into class label for this model

This is usually the same value shown again in `threshold_config.threshold`.

### `leaderboard_metrics.validation_pr_auc`

- Type: `number`
- Meaning: Precision-Recall AUC on the validation split

This is the most important ranking metric in the current model-selection policy.

Higher is better.

### `leaderboard_metrics.validation_roc_auc`

- Type: `number`
- Meaning: ROC-AUC on the validation split

Useful as a secondary ranking metric.

Higher is better.

### `leaderboard_metrics.validation_brier_score`

- Type: `number`
- Meaning: probability calibration error on the validation split

Lower is better.

This is used as a tie-breaker when PR-AUC values are close.

### `leaderboard_metrics.validation_precision`

- Type: `number`
- Meaning: precision on validation after applying the chosen threshold

Interpretation:
- of the companies the model flags as risky, how many are actually positive

Higher is better when false positives are costly.

### `leaderboard_metrics.validation_recall`

- Type: `number`
- Meaning: recall on validation after applying the chosen threshold

Interpretation:
- of the actual positive cases, how many the model successfully catches

Higher is better when missing risky companies is costly.

### `leaderboard_metrics.validation_f1`

- Type: `number`
- Meaning: F1 score on validation after applying the chosen threshold

This balances precision and recall into one threshold-based metric.

### `leaderboard_metrics.test_pr_auc`

- Type: `number`
- Meaning: Precision-Recall AUC on the held-out test split

Use this to judge how well the validation result generalizes.

### `leaderboard_metrics.test_roc_auc`

- Type: `number`
- Meaning: ROC-AUC on the held-out test split

### `leaderboard_metrics.test_brier_score`

- Type: `number`
- Meaning: calibration error on the held-out test split

### `leaderboard_metrics.test_precision`

- Type: `number`
- Meaning: thresholded precision on the test split

### `leaderboard_metrics.test_recall`

- Type: `number`
- Meaning: thresholded recall on the test split

### `leaderboard_metrics.test_f1`

- Type: `number`
- Meaning: thresholded F1 on the test split

---

## `threshold_config`

This object comes from the model’s saved threshold JSON.

Current fields:

- `model_name`
- `threshold`
- `threshold_version`

### `threshold_config.model_name`

- Type: `string`
- Meaning: model identifier repeated inside the threshold file

### `threshold_config.threshold`

- Type: `number`
- Meaning: the selected probability cutoff for this model

The scoring flow compares:
- `probability >= threshold` => positive class
- `probability < threshold` => negative class

### `threshold_config.threshold_version`

- Type: `string`
- Example: `v1`
- Meaning: version label for the threshold configuration

Useful for tracking changes if threshold selection logic changes later.

---

## `feature_config`

This object comes from the model’s saved feature JSON.

Current fields:

- `model_name`
- `input_columns`
- `numeric_columns`
- `categorical_columns`
- `transformed_feature_names`
- `feature_list_version`

### `feature_config.model_name`

- Type: `string`
- Meaning: model identifier repeated inside the feature config file

### `feature_config.input_columns`

- Type: `array<string>`
- Meaning: the raw columns expected before preprocessing

These are the columns fed into the sklearn pipeline before:
- imputation
- one-hot encoding
- scaling (for linear models)

This is the most useful field when explaining what the model consumes.

### `feature_config.numeric_columns`

- Type: `array<string>`
- Meaning: the subset of raw input columns treated as numeric during preprocessing

These go through numeric imputation and then directly into the model pipeline.

### `feature_config.categorical_columns`

- Type: `array<string>`
- Meaning: the subset of raw input columns treated as categorical

Currently this is mainly used for `sector`.

### `feature_config.transformed_feature_names`

- Type: `array<string>`
- Meaning: the fully expanded post-preprocessing feature names

This includes:
- numeric features after preprocessing
- one-hot encoded categorical columns (for example sector expansions)

This is the real feature space seen by the trained estimator.

### `feature_config.feature_list_version`

- Type: `string`
- Example: `v1`
- Meaning: version label for the feature schema

Useful when the engineered feature set changes over time.

---

## `validation_metrics`

This object contains the full validation metric bundle saved by training.

Current fields:

- `threshold`
- `roc_auc`
- `pr_auc`
- `accuracy`
- `precision`
- `recall`
- `f1`
- `balanced_accuracy`
- `brier_score`
- `confusion_matrix`

This overlaps with `leaderboard_metrics`, but the naming is cleaner and it also includes `accuracy`, `balanced_accuracy`, and `confusion_matrix`.

### `validation_metrics.threshold`

- Type: `number`
- Meaning: threshold used when computing threshold-based validation metrics

### `validation_metrics.roc_auc`

- Type: `number`
- Meaning: validation ROC-AUC

### `validation_metrics.pr_auc`

- Type: `number`
- Meaning: validation PR-AUC

### `validation_metrics.accuracy`

- Type: `number`
- Meaning: share of correct predictions on validation after thresholding

### `validation_metrics.precision`

- Type: `number`
- Meaning: validation precision after thresholding

### `validation_metrics.recall`

- Type: `number`
- Meaning: validation recall after thresholding

### `validation_metrics.f1`

- Type: `number`
- Meaning: validation F1 after thresholding

### `validation_metrics.balanced_accuracy`

- Type: `number`
- Meaning: class-balanced accuracy on validation

This matters because balanced accuracy reduces the distortion of class imbalance.

### `validation_metrics.brier_score`

- Type: `number`
- Meaning: calibration quality of predicted probabilities on validation

Lower is better.

### `validation_metrics.confusion_matrix`

- Type: `array<array<number>>`
- Shape: `[[TN, FP], [FN, TP]]`
- Meaning: raw confusion-matrix counts on validation

Useful when you want a fully transparent model review panel.

---

## `test_metrics`

This object has the same structure as `validation_metrics`, but on the held-out test split.

Current fields:

- `threshold`
- `roc_auc`
- `pr_auc`
- `accuracy`
- `precision`
- `recall`
- `f1`
- `balanced_accuracy`
- `brier_score`
- `confusion_matrix`

Use this to show how the model performs on unseen data.

### Why both validation and test metrics matter

- `validation_metrics` are used during model selection and threshold tuning
- `test_metrics` are used to estimate how well that chosen configuration generalizes

If validation is strong but test is weak, the model is likely overfitting.

---

## Recommended frontend interpretation blocks

For each model, your frontend should communicate:

1. **Identity**
- model name
- whether it is production

2. **Selection status**
- why it is production or why it remains only a benchmark

3. **Ranking quality**
- PR-AUC
- ROC-AUC

4. **Threshold behavior**
- threshold
- precision
- recall

5. **Stability / confidence**
- Brier score
- test-vs-validation comparison

6. **Feature transparency**
- input column count
- transformed feature count
- feature schema version

---

## Summary sentence you can use in the UI

“Each model card shows the trained artifact, threshold, feature schema, validation behavior, and held-out test performance so the active production model can be compared transparently against every benchmark model in the registry.”
