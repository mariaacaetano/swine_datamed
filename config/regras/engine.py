from bulario.clinical_input import context_adjustment, extract_clinical_case
from bulario.models import Doenca
from bulario.contracts import inference_result
from bulario.utils import clinical_symptoms


class MotorRegras:
    """Seleção por regras explícitas e ranqueamento por pontuação heurística.

    Percorre as enfermidades uma vez, sem encadeamento ou derivação de fatos.
    A pontuação combina cobertura, precisão e ajustes clínicos manuais;
    não representa uma probabilidade clínica estimada.
    """

    nome = "regras"
    # Constantes heurísticas da implementação, sem calibração clínica ou
    # análise de sensibilidade documentada. A cobertura pode favorecer
    # enfermidades com poucos sintomas cadastrados.
    PESO_COBERTURA = 0.6
    PESO_PRECISAO = 0.4
    PESO_AJUSTE_CLINICO = 0.25

    def inferir(self, texto, limite=5, incluir_indicacoes=True):
        return self.inferir_caso(extract_clinical_case(texto), limite, incluir_indicacoes)

    def inferir_caso(self, caso, limite=5, incluir_indicacoes=True):
        sintomas = caso["sintomas"]
        reconhecidos = {sintoma.id for sintoma in sintomas}
        hipoteses = []

        for doenca in Doenca.objects.prefetch_related("sintomas"):
            sintomas_doenca = clinical_symptoms(doenca)
            correspondentes = [item for item in sintomas_doenca if item.id in reconhecidos]
            # Regra de seleção: somente candidatas com evidência positiva.
            if not correspondentes:
                continue
            cobertura = len(correspondentes) / max(len(sintomas_doenca), 1)
            precisao = len(correspondentes) / max(len(sintomas), 1)
            score_sintomas = (self.PESO_COBERTURA * cobertura) + (self.PESO_PRECISAO * precisao)
            score = max(0, min(1, score_sintomas + (self.PESO_AJUSTE_CLINICO * context_adjustment(doenca, caso))))
            hipoteses.append(self._hipotese(doenca, score, correspondentes))

        hipoteses.sort(key=lambda item: (-item["score"], item["nome"]))
        hipoteses = hipoteses[:limite]
        return self._resultado(caso, hipoteses, incluir_indicacoes)

    @staticmethod
    def _hipotese(doenca, score, evidencias):
        return {
            "id": doenca.id,
            "nome": doenca.nome,
            "tipo": doenca.tipo,
            "fase_comum": doenca.fase_comum,
            "score": round(score, 6),
            "evidencias": [item.nome for item in evidencias],
        }

    def _resultado(self, caso, hipoteses, incluir_indicacoes=True):
        return inference_result(caso, hipoteses, self.nome, incluir_indicacoes,
                                tipo_score="pontuacao_heuristica", calibracao_clinica=False)
