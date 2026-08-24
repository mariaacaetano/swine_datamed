import json
import platform
import time
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


ID_COLUMNS = ["observacao_id", "combinacao_id"]
TARGET = "doenca_alvo"
CORE_CLINICAL_COLUMNS = [
    "Temperatura corporal (°C)", "Idade", "Gênero", "Fase reprodutiva",
    "Estado reprodutivo", "Duração dos sintomas",
]


def _load(path):
    frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
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


def train_and_evaluate(data_dir, artifact_dir, seed=42):
    data_dir, artifact_dir = Path(data_dir), Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    x_train, y_train = _load(data_dir / "treino.csv")
    x_validation, y_validation = _load(data_dir / "validacao.csv")
    x_test, y_test = _load(data_dir / "teste.csv")

    symptom_columns = [name for name in x_train if name.startswith("sintoma_")]
    categorical_columns = [name for name in CORE_CLINICAL_COLUMNS if name in x_train]
    feature_columns = [*symptom_columns, *categorical_columns]
    x_train = x_train[feature_columns]
    x_validation = x_validation[feature_columns]
    x_test = x_test[feature_columns]
    preprocessor = ColumnTransformer([
        ("symptoms", "passthrough", symptom_columns),
        ("clinical", OneHotEncoder(handle_unknown="ignore", sparse_output=True), categorical_columns),
    ])
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
    validation_results = {}
    for name, model in candidates.items():
        candidate_start = time.perf_counter()
        model.fit(train_matrix, y_train)
        metrics, _ = _metrics(model, validation_matrix, y_validation)
        metrics["tempo_treinamento_s"] = round(time.perf_counter() - candidate_start, 3)
        validation_results[name] = metrics

    winner_name = max(validation_results, key=lambda name: validation_results[name]["f1_macro"])
    winner = candidates[winner_name]
    from scipy.sparse import vstack
    winner.fit(vstack([train_matrix, validation_matrix]), pd.concat([y_train, y_validation]))
    test_metrics, test_prediction = _metrics(winner, test_matrix, y_test)
    labels = sorted(set(y_test) | set(test_prediction))
    report = classification_report(y_test, test_prediction, labels=labels, output_dict=True, zero_division=0)
    matrix = confusion_matrix(y_test, test_prediction, labels=labels)

    metadata = {
        "criado_em": datetime.now(timezone.utc).isoformat(),
        "semente": seed,
        "modelo_selecionado": winner_name,
        "criterio_selecao": "f1_macro_validacao",
        "registros": {"treino": len(y_train), "validacao": len(y_validation), "teste": len(y_test)},
        "atributos": {"sintomas": len(symptom_columns), "clinicos": len(categorical_columns)},
        "resultados_validacao": validation_results,
        "resultado_teste": test_metrics,
        "classes_teste": labels,
        "matriz_confusao": matrix.tolist(),
        "relatorio_classes": report,
        "versoes": {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                    "pandas": pd.__version__, "numpy": np.__version__},
        "tempo_pipeline_s": round(time.perf_counter() - started, 3),
    }
    artifact = {
        "preprocessor": preprocessor,
        "model": winner,
        "feature_columns": feature_columns,
        "symptom_columns": symptom_columns,
        "categorical_columns": categorical_columns,
        "metadata": metadata,
    }
    joblib.dump(artifact, artifact_dir / "model.joblib", compress=3)
    with (artifact_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    return metadata
