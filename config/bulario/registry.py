from dataclasses import dataclass
from typing import Protocol
from pickle import UnpicklingError

from rest_framework.exceptions import APIException


DEFAULT_ENGINE = "machine_learning"


class InferenceEngine(Protocol):
    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True): ...


class ModelUnavailable(APIException):
    status_code = 503
    default_detail = "O modelo de inferência está indisponível. Verifique os artefatos no servidor."


@dataclass(frozen=True)
class EngineDefinition:
    key: str
    label: str
    engine: type


def engine_registry():
    from machine.engine import MotorMachineLearning, MotorMachineLearningK10, MotorMachineLearningK100
    from regras.engine import MotorRegras
    from regras.chaining import MotorRegrasEncadeadas
    from semantica.engine import MotorSemantico
    from .knowledge_engines import MotorBayesiano, MotorFuzzy, MotorFuzzySanchez

    return {definition.key: definition for definition in [
        EngineDefinition("machine_learning", "Naive Bayes supervisionado", MotorMachineLearning),
        EngineDefinition("machine_learning_k10", "Random Forest com estados", MotorMachineLearningK10),
        EngineDefinition("machine_learning_k100", "Naive Bayes histórico (k=100)", MotorMachineLearningK100),
        EngineDefinition("regras", "Regras heurísticas", MotorRegras),
        EngineDefinition("regras_encadeadas", "Regras com encadeamento", MotorRegrasEncadeadas),
        EngineDefinition("semantica", "Grafo e Jaccard", MotorSemantico),
        EngineDefinition("rede_bayesiana", "Naive Bayes parametrizado", MotorBayesiano),
        EngineDefinition("fuzzy", "Fuzzy Sugeno", MotorFuzzy),
        EngineDefinition("fuzzy_sanchez", "Fuzzy Sanchez", MotorFuzzySanchez),
    ]}


def model_status(key):
    definition = engine_registry()[key]
    motor = definition.engine
    status = {"id": key, "nome": definition.label, "padrao": key == DEFAULT_ENGINE,
              "disponivel": True, "schema": "caso_clinico_v1"}
    if hasattr(motor, "artifact_path"):
        try:
            artifact = motor._load_artifact()
        except (OSError, ValueError, EOFError, KeyError, ImportError, UnpicklingError):
            artifact = None
        status["disponivel"] = artifact is not None
        if artifact:
            metadata = artifact["metadata"]
            status.update({"modelo": metadata.get("modelo_selecionado"),
                           "versao": metadata.get("criado_em"),
                           "schema": metadata.get("schema_entrada", "sintomas_binarios"),
                           "versao_base_treino": metadata.get("versao_base"),
                           "versoes_treino": metadata.get("versoes", {})})
    return status
