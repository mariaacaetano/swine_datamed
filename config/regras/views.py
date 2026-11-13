from bulario.views import TriagemView


class InferenciaRegrasView(TriagemView):
    engine_key = "regras"


class InferenciaRegrasEncadeadasView(TriagemView):
    engine_key = "regras_encadeadas"
