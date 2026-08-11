from django.conf import settings
from time import perf_counter
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .data_pipeline import generate_clinical_dataset, generate_dataset, import_base_data
from .models import CasoClinico, Doenca, Farmaco, GeracaoDataset, Sintoma, Vacina, Variavel
from .serializers import (CasoClinicoSerializer, DoencaSerializer, FarmacoSerializer,
                          GeracaoDatasetSerializer, SintomaSerializer, VacinaSerializer, VariavelSerializer)
from .utils import normalize, score_farmaco


def disease_hints_for_query(query):
    normalized_query = normalize(query)
    if not normalized_query:
        return []

    hints = set()

    for sintoma in Sintoma.objects.prefetch_related("doencas"):
        symptom = normalize(sintoma.nome)
        if symptom and (symptom in normalized_query or normalized_query in symptom):
            hints.update(sintoma.doencas.all())

    for doenca in Doenca.objects.all():
        text = normalize(" ".join([doenca.nome, doenca.sintomas_texto, doenca.tipo, doenca.fase_comum]))
        if normalized_query in text:
            hints.add(doenca)

    return list(hints)


class FarmacoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Farmaco.objects.prefetch_related("doencas_relacionadas").all()
    serializer_class = FarmacoSerializer
    lookup_field = "id"

    @action(detail=False, methods=["get"])
    def buscar(self, request):
        query = request.query_params.get("q", "")
        disease_hints = disease_hints_for_query(query)
        scored = [
            (farmaco, score_farmaco(farmaco, query, disease_hints))
            for farmaco in self.get_queryset()
        ]
        results = [
            farmaco
            for farmaco, score in sorted(scored, key=lambda item: (-item[1], item[0].nome_comercial))
            if score > 0
        ]

        return Response(
            {
                "query": query,
                "disease_hints": DoencaSerializer(disease_hints, many=True).data,
                "results": FarmacoSerializer(results, many=True).data,
            }
        )


class SintomaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Sintoma.objects.prefetch_related("doencas").all()
    serializer_class = SintomaSerializer


class DoencaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Doenca.objects.prefetch_related("sintomas").all()
    serializer_class = DoencaSerializer


class VariavelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variavel.objects.all()
    serializer_class = VariavelSerializer


class VacinaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vacina.objects.all()
    serializer_class = VacinaSerializer


class CasoClinicoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CasoClinico.objects.select_related("doenca", "geracao").all()
    serializer_class = CasoClinicoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        generation = self.request.query_params.get("geracao")
        return queryset.filter(geracao_id=generation) if generation else queryset


class PreparacaoDadosView(APIView):
    """Seção do backend para importar a base e construir o dataset reproduzível."""

    def get(self, request):
        latest = GeracaoDataset.objects.first()
        return Response({
            "base": {"doencas": Doenca.objects.count(), "sintomas": Sintoma.objects.count(),
                     "variaveis": Variavel.objects.count(), "farmacos": Farmaco.objects.count(), "vacinas": Vacina.objects.count()},
            "ultima_geracao": GeracaoDatasetSerializer(latest).data if latest else None,
        })

    def post(self, request):
        try:
            raw_total = request.data.get("total")
            total, seed = (int(raw_total) if raw_total not in (None, "") else None), int(request.data.get("semente", 42))
            variations = int(request.data.get("variacoes", 10))
            summary = import_base_data(settings.BASE_DIR.parent / "base_data", clear=bool(request.data.get("limpar", False)))
            generation = generate_dataset(settings.BASE_DIR.parent / "generated_data" / "dataset_combinacoes_sintomas.csv", total=total, seed=seed)
            clinical = generate_clinical_dataset(
                settings.BASE_DIR.parent / "generated_data" / "dataset_clinico_ampliado.csv",
                variations_per_combination=variations, seed=seed, replace=False,
            )
        except (TypeError, ValueError, OSError) as exc:
            return Response({"erro": str(exc)}, status=400)
        return Response({"base": summary, "combinacoes": GeracaoDatasetSerializer(generation).data,
                         "dataset_clinico": GeracaoDatasetSerializer(clinical).data}, status=201)


class TriagemView(APIView):
    def post(self, request):
        from machine.engine import MotorMachineLearning
        from regras.engine import MotorRegras
        from semantica.engine import MotorSemantico

        mecanismos = {
            "regras": MotorRegras,
            "semantica": MotorSemantico,
            "machine_learning": MotorMachineLearning,
        }
        nome = request.data.get("mecanismo", "regras")
        if nome not in mecanismos:
            return Response({"erro": "Mecanismo inválido."}, status=400)
        texto = request.data.get("texto", "").strip()
        contexto = request.data.get("contexto_clinico", "").strip()
        sintoma_perguntado = request.data.get("sintoma_perguntado", "").strip()
        texto_clinico = _compose_clinical_text(contexto, texto, sintoma_perguntado)
        resultado = mecanismos[nome]().inferir(texto_clinico)
        pergunta = _next_clinical_question(resultado)
        resultado["contexto_clinico"] = texto_clinico
        resultado["pergunta_complementar"] = pergunta
        resultado["resposta"] = _formatar_resposta(resultado)
        resultado["aviso"] = "Apoio à triagem; não substitui avaliação de médico-veterinário."
        return Response(resultado)


def _compose_clinical_text(context, answer, asked_symptom):
    normalized_answer = normalize(answer).strip()
    interpreted = answer
    if asked_symptom:
        negative = normalized_answer.startswith(("nao", "negativo", "ausente", "sem "))
        affirmative = normalized_answer.startswith(("sim", "positivo", "apresenta", "tem "))
        if negative:
            interpreted = f"não apresenta {asked_symptom}. {answer}"
        elif affirmative:
            interpreted = f"apresenta {asked_symptom}. {answer}"
    return "\n".join(part for part in [context, interpreted] if part).strip()


def _next_clinical_question(result):
    hypotheses = result.get("hipoteses", [])
    if len(hypotheses) < 2:
        return None
    diseases = list(Doenca.objects.prefetch_related("sintomas").filter(
        id__in=[item["id"] for item in hypotheses]
    ))
    known = {normalize(name) for name in [
        *result.get("sintomas_reconhecidos", []), *result.get("sintomas_negados", [])
    ]}
    rank = {item["id"]: index for index, item in enumerate(hypotheses)}
    candidates = {}
    for disease in diseases:
        weight = len(hypotheses) - rank.get(disease.id, len(hypotheses))
        for symptom in disease.sintomas.all():
            if normalize(symptom.nome) in known:
                continue
            item = candidates.setdefault(symptom.id, {"symptom": symptom, "diseases": set(), "weight": 0})
            item["diseases"].add(disease.id)
            item["weight"] += weight
    total = len(hypotheses)
    eligible = [item for item in candidates.values() if 0 < len(item["diseases"]) < total]
    if not eligible:
        return None
    selected = max(
        eligible,
        key=lambda item: (len(item["diseases"]) * (total - len(item["diseases"])), item["weight"]),
    )["symptom"]
    duration = result.get("variaveis_reconhecidas", {}).get("duracao_categoria")
    prefix = f"Durante o período observado ({duration}), " if duration else "Durante o período observado, "
    return {
        "sintoma": selected.nome,
        "texto": f"{prefix}o animal também apresentou {selected.nome.lower()}? Responda sim ou não e acrescente outros sinais observados.",
    }


class ComparacaoInferenciaView(APIView):
    """Executa a mesma entrada nos três motores e mede o custo da inferência."""

    def post(self, request):
        from machine.engine import MotorMachineLearning
        from regras.engine import MotorRegras
        from semantica.engine import MotorSemantico

        texto = request.data.get("texto", "").strip()
        if not texto:
            return Response({"erro": "Informe um texto para comparação."}, status=400)
        motores = [MotorRegras(), MotorSemantico(), MotorMachineLearning()]
        resultados = []
        for motor in motores:
            inicio = perf_counter()
            resultado = motor.inferir(texto)
            tempo_s = perf_counter() - inicio
            resultados.append({
                **resultado,
                "metricas_sistema": {
                    "tempo_resposta_s": round(tempo_s, 5),
                    "sintomas_reconhecidos": len(resultado["sintomas_reconhecidos"]),
                    "hipoteses_retornadas": len(resultado["hipoteses"]),
                    "farmacos_retornados": len(resultado["farmacos_relacionados"]),
                    "variaveis_reconhecidas": sum(
                        value not in (None, "") for value in resultado["variaveis_reconhecidas"].values()
                    ),
                },
            })
        primeiros = [item["hipoteses"][0]["nome"] for item in resultados if item["hipoteses"]]
        return Response({
            "entrada": texto,
            "resultados": resultados,
            "concordancia_top_1": len(primeiros) == len(resultados) and len(set(primeiros)) == 1,
            "observacao_metricas_preditivas": (
                "Precisão, recall e acurácia exigem casos rotulados e não são calculados nesta consulta isolada."
            ),
        })


def _formatar_resposta(resultado):
    sintomas = resultado["sintomas_reconhecidos"]
    hipoteses = resultado["hipoteses"]
    if not hipoteses:
        return (
            "Ainda não encontrei uma hipótese forte. Informe outros sinais, "
            "idade, fase produtiva, temperatura e evolução do caso."
        )
    linhas = [f"{indice}. {item['nome']}" for indice, item in enumerate(hipoteses, 1)]
    medicamentos = resultado["farmacos_relacionados"]
    bloco_medicamentos = ""
    if medicamentos:
        itens = [
            f"- {item['nome_comercial']}: {item['principio_ativo'] or 'princípio ativo não informado'}"
            for item in medicamentos
        ]
        bloco_medicamentos = "\n\nFármacos relacionados na base:\n" + "\n".join(itens)
    reconhecidos = f"Sintomas reconhecidos: {', '.join(sintomas)}.\n\n" if sintomas else ""
    variables = resultado.get("variaveis_reconhecidas", {})
    labels = {
        "temperatura_corporal_c": "temperatura",
        "classificacao_temperatura": "faixa térmica",
        "fase_reprodutiva": "fase",
        "genero": "gênero",
        "estado_reprodutivo": "estado reprodutivo",
        "idade_categoria": "idade",
        "duracao_categoria": "duração",
    }
    context = [f"{labels[key]}: {value}" for key, value in variables.items()
               if key in labels and value not in (None, "")]
    context_block = f"Contexto considerado: {'; '.join(context)}.\n\n" if context else ""
    alert_block = "".join(f"Alerta: {alert}\n" for alert in resultado.get("alertas", []))
    question = resultado.get("pergunta_complementar")
    question_block = f"\n\nPara refinar a triagem:\n{question['texto']}" if question else ""
    return (
        reconhecidos
        + context_block
        + alert_block
        + f"Hipóteses pelo mecanismo de {resultado['mecanismo']}:\n"
        + "\n".join(linhas)
        + bloco_medicamentos
        + question_block
        + "\n\nAtenção: apoio à triagem; valide a decisão com médico-veterinário."
    )
