from collections import defaultdict

from bulario.clinical_input import context_adjustment, extract_clinical_case
from bulario.models import Doenca
from bulario.contracts import inference_result
from bulario.utils import clinical_symptoms


class MotorSemantico:
    """Consulta arestas diretas Sintoma -> Doença e ranqueia por Jaccard.

    Obtém a mesma interseção do motor heurístico por consulta inversa.
    Não executa inferência multissalto nem propagação; os fármacos são
    recuperados após o ranking. A comparação muda consulta e métrica,
    portanto não isola o efeito da representação em grafo.
    """

    nome = "semantica"

    def inferir(self, texto, limite=5, incluir_indicacoes=True):
        return self.inferir_caso(extract_clinical_case(texto), limite, incluir_indicacoes)

    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True):
        sintomas = caso["sintomas"]
        correspondencias = defaultdict(list)
        for sintoma in sintomas:
            for doenca in sintoma.doencas.all():
                correspondencias[doenca.id].append(sintoma.nome)

        doencas = {
            item.id: item
            for item in Doenca.objects.prefetch_related("sintomas").filter(id__in=correspondencias)
        }
        hipoteses = []
        for doenca_id, evidencias in correspondencias.items():
            doenca = doencas[doenca_id]
            total_doenca = len(clinical_symptoms(doenca))
            uniao = len(sintomas) + total_doenca - len(evidencias)
            # Uma candidata tem ao menos uma aresta, logo a união é positiva.
            similaridade = len(evidencias) / uniao
            score = max(0, min(1, similaridade + (0.25 * context_adjustment(doenca, caso))))
            hipoteses.append({
                "id": doenca.id,
                "nome": doenca.nome,
                "tipo": doenca.tipo,
                "fase_comum": doenca.fase_comum,
                "score": round(score, 6),
                "evidencias": evidencias,
                "arestas_semanticas": [f"{nome} -> {doenca.nome}" for nome in evidencias],
            })

        # Alias legado: cada entrada representa uma única aresta.
        for hipotese in hipoteses:
            hipotese["caminhos_semanticos"] = hipotese["arestas_semanticas"]

        hipoteses.sort(key=lambda item: (-item["score"], item["nome"]))
        hipoteses = hipoteses[:limite]
        return inference_result(caso, hipoteses, self.nome, incluir_indicacoes,
                                tipo_score="similaridade_ajustada", calibracao_clinica=False)
