import json
import platform
import time
import os
import tempfile
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             precision_recall_fscore_support, top_k_accuracy_score)
from sklearn.naive_bayes import BernoulliNB
from sklearn.preprocessing import OneHotEncoder
from sklearn.linear_model import SGDClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from .observations import INPUT_SCHEMA, SYMPTOM_STATES, validate_split_groups
from bulario.utils import is_clinical_symptom


ID_COLUMNS = ["observacao_id", "combinacao_id"]
TARGET = "doenca_alvo"
CORE_CLINICAL_COLUMNS = [
    "Temperatura corporal (°C)", "Idade", "Gênero", "Fase reprodutiva",
    "Estado reprodutivo", "Duração dos sintomas",
]


def _load(path):
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    binary_columns = [c for c in frame if c.startswith('sintoma_')
                      and is_clinical_symptom(c.split('_', 2)[2])]
    if binary_columns and not any(c.startswith('estado_sintoma_') for c in frame):
        frame = frame.loc[frame[binary_columns].eq(1).any(axis=1)].copy()
    if frame.empty:
        raise ValueError('A partição não contém observações com sinais documentados.')
    y = frame.pop(TARGET).astype(str)
    return frame.drop(columns=ID_COLUMNS, errors="ignore"), y


def _metrics(model, x, y):
    prediction = model.predict(x)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, prediction, average="macro", zero_division=0,
    )
    result = {
        "acuracia": float(accuracy_score(y, prediction)),
        "precisao_macro": float(precision),
        "recall_macro": float(recall),
        "f1_macro": float(f1),
    }
    scores = None
    if hasattr(model, "predict_proba"):
        scores = model.predict_proba(x)
    elif hasattr(model, "decision_function"):
        scores = model.decision_function(x)
    if scores is not None and len(model.classes_) >= 5:
        result["acuracia_top_5"] = float(top_k_accuracy_score(
            y, scores, k=5, labels=model.classes_,
        ))
    return result, prediction


def train_and_evaluate(data_dir, artifact_dir, seed=42, model_name=None):
    data_dir, artifact_dir = Path(data_dir), Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    x_train, y_train = _load(data_dir / "treino.csv")
    x_validation, y_validation = _load(data_dir / "validacao.csv")
    x_test, y_test = _load(data_dir / "teste.csv")

    state_columns = [name for name in x_train if name.startswith("estado_sintoma_")
                     and is_clinical_symptom(name.split('_', 3)[3])]
    symptom_columns = [] if state_columns else [name for name in x_train if name.startswith("sintoma_")
                     and is_clinical_symptom(name.split('_', 2)[2])]
    if state_columns:
        validate_split_groups(data_dir)
        for frame in [x_train, x_validation, x_test]:
            if not frame[state_columns].isin(SYMPTOM_STATES).all().all():
                raise ValueError("Estado de sintoma inválido no conjunto de treinamento.")
    categorical_columns = [name for name in CORE_CLINICAL_COLUMNS if name in x_train]
    feature_columns = [*symptom_columns, *state_columns, *categorical_columns]
    x_train = x_train[feature_columns]
    x_validation = x_validation[feature_columns]
    x_test = x_test[feature_columns]
    transformers = [("states", OneHotEncoder(categories=[SYMPTOM_STATES] * len(state_columns),
                        handle_unknown="error", sparse_output=True), state_columns)] if state_columns else [
                        ("symptoms", "passthrough", symptom_columns)]
    transformers.append(("clinical", OneHotEncoder(handle_unknown="ignore", sparse_output=True), categorical_columns))
    preprocessor = ColumnTransformer(transformers)
    started = time.perf_counter()
    train_matrix = preprocessor.fit_transform(x_train)
    validation_matrix = preprocessor.transform(x_validation)
    test_matrix = preprocessor.transform(x_test)

    candidates = {
        "Bernoulli Naive Bayes": BernoulliNB(alpha=1.0),
        "Regressão Logística (SGD)": SGDClassifier(
            loss="log_loss", alpha=0.0001, max_iter=1000, tol=1e-3,
            class_weight="balanced", random_state=seed, n_jobs=-1,
        ),
        "Árvore de Decisão": DecisionTreeClassifier(
            max_depth=35, min_samples_leaf=2, class_weight="balanced", random_state=seed,
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=160, max_depth=35, min_samples_leaf=2,
            class_weight="balanced_subsample", random_state=seed, n_jobs=-1,
        ),
    }
    if model_name:
        if model_name not in candidates:
            raise ValueError(f"Modelo desconhecido: {model_name}")
        candidates = {model_name: candidates[model_name]}
    validation_results = {}
    for name, model in candidates.items():
        candidate_start = time.perf_counter()
        model.fit(train_matrix, y_train)
        metrics, _ = _metrics(model, validation_matrix, y_validation)
        metrics["tempo_treinamento_s"] = round(time.perf_counter() - candidate_start, 3)
        validation_results[name] = metrics

    winner_name = max(validation_results, key=lambda name: validation_results[name]["f1_macro"])
    winner = candidates[winner_name]
    from scipy.sparse import issparse, vstack
    combined = vstack([train_matrix, validation_matrix]) if issparse(train_matrix) else np.vstack([train_matrix, validation_matrix])
    winner.fit(combined, pd.concat([y_train, y_validation]))
    test_metrics, test_prediction = _metrics(winner, test_matrix, y_test)
    labels = sorted(set(y_test) | set(test_prediction))
    report = classification_report(y_test, test_prediction, labels=labels, output_dict=True, zero_division=0)
    matrix = confusion_matrix(y_test, test_prediction, labels=labels)

    metadata = {
        "sha256_datasets": {split: hashlib.sha256((data_dir / f"{split}.csv").read_bytes()).hexdigest()
                            for split in ["treino", "validacao", "teste"]},
        "criado_em": datetime.now(timezone.utc).isoformat(),
        "semente": seed,
        "modelo_selecionado": winner_name,
        "criterio_selecao": "modelo_explicito" if model_name else "f1_macro_validacao",
        "schema_entrada": INPUT_SCHEMA if state_columns else "sintomas_binarios",
        "registros": {"treino": len(y_train), "validacao": len(y_validation), "teste": len(y_test)},
        "atributos": {"sintomas": len(state_columns or symptom_columns), "clinicos": len(categorical_columns)},
        "resultados_validacao": validation_results,
        "resultado_teste": test_metrics,
        "classes_teste": labels,
        "matriz_confusao": matrix.tolist(),
        "relatorio_classes": report,
        "versoes": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                    "pandas": pd.__version__, "numpy": np.__version__},
        "tempo_pipeline_s": round(time.perf_counter() - started, 3),
    }
    source_metadata = data_dir / "metadados.json"
    if source_metadata.exists():
        metadata["origem_dataset"] = json.loads(source_metadata.read_text(encoding="utf-8"))
    metadata["versao_base"] = metadata.get("origem_dataset", {}).get("versao_base")
    artifact = {
        "preprocessor": preprocessor,
        "model": winner,
        "feature_columns": feature_columns,
        "symptom_columns": symptom_columns,
        "symptom_state_columns": state_columns,
        "categorical_columns": categorical_columns,
        "metadata": metadata,
    }
    with tempfile.NamedTemporaryFile(dir=artifact_dir, suffix=".joblib", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        joblib.dump(artifact, temporary_path, compress=3)
        os.replace(temporary_path, artifact_dir / "model.joblib")
    finally:
        temporary_path.unlink(missing_ok=True)
    with (artifact_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    return metadata
