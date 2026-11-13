"""Critério único de completude para importar e disponibilizar fármacos."""
import re

from django.db.models import Q


MEDICATION_FIELDS = {
    "nome_comercial": "Nome comercial",
    "principio_ativo": "Princípio ativo",
    "classe": "Classe",
    "indicacoes_principais": "Indicações principais",
    "posologia": "Posologia",
    "via_administracao": "Via administração",
    "carencia": "Carência",
    "contraindicacoes": "Contraindicações",
    "reacoes_adversas": "Reações adversas",
    "mecanismo_acao": "Mecanismo de ação",
    "precaucoes": "Precauções",
}

# Ausência explicitamente documentada (como "Não apresenta") é informação válida.
# Identificador e URL externa da bula não integram os campos obrigatórios da ficha.
MISSING_VALUES = (
    "", "-", "–", "—", "...", "completar", "a completar", "a preencher",
    "pendente", "a definir", "na", "n/a", "null", "none", "não informado",
    "nao informado", "não informada", "nao informada", "não informado no documento",
    "nao informado no documento", "não especificado", "nao especificado",
    "não disponível", "nao disponivel", "sem informação", "sem informacao",
)
MISSING_PATTERN = r"^\s*(?:[-–—.]+|" + "|".join(re.escape(value) for value in MISSING_VALUES) + r")\s*[.;]*\s*$"
_missing_value = re.compile(MISSING_PATTERN, re.IGNORECASE)


def missing_medication_fields(values, *, csv_row=False):
    """Retorna as chaves dos campos faltantes; não cria conteúdo substituto."""
    return [field for field, column in MEDICATION_FIELDS.items()
            if values.get(column if csv_row else field) is None
            or _missing_value.fullmatch(str(values.get(column if csv_row else field))) is not None]


def complete_medication_condition(prefix=""):
    """Usa o mesmo padrão da importação também em consultas e relações SQL."""
    condition = Q()
    for field in MEDICATION_FIELDS:
        key = prefix + field
        condition &= Q(**{key + "__isnull": False}) & ~Q(**{key + "__iregex": MISSING_PATTERN})
    return condition


def audit_medication_rows(rows):
    accepted, blocked = [], []
    for row in rows:
        missing = missing_medication_fields(row, csv_row=True)
        item = {"id_origem": row.get("ID"), "nome_comercial": row.get("Nome comercial", "")}
        if missing:
            blocked.append({**item, "campos_ausentes": [MEDICATION_FIELDS[field] for field in missing]})
        else:
            accepted.append(item)
    accepted_names = {item["nome_comercial"].strip().casefold() for item in accepted}
    blocked_names = {item["nome_comercial"].strip().casefold() for item in blocked}
    return {"criterio": "Todos os campos da ficha farmacológica preenchidos; link da bula opcional.",
            "campos_obrigatorios": list(MEDICATION_FIELDS.values()),
            "aprovados": accepted, "bloqueados": blocked,
            "total_aprovados": len(accepted), "total_bloqueados": len(blocked),
            "total_farmacos_aprovados": len(accepted_names),
            "total_farmacos_bloqueados": len(blocked_names - accepted_names)}
