"""Fichas fictícias completas, usadas somente nos bancos temporários dos testes."""


def complete_medication_data(**overrides):
    values = {
        "nome_comercial": "Produto fictício de teste",
        "principio_ativo": "Princípio ativo de teste",
        "classe": "Classe de teste",
        "indicacoes_principais": "Associação fictícia do cenário de teste",
        "posologia": "Posologia preenchida na ficha fictícia",
        "via_administracao": "Via preenchida na ficha fictícia",
        "carencia": "Carência preenchida na ficha fictícia",
        "contraindicacoes": "Não apresenta",
        "reacoes_adversas": "Não apresenta",
        "mecanismo_acao": "Mecanismo descrito na ficha fictícia",
        "precaucoes": "Precauções descritas na ficha fictícia",
    }
    return {**values, **overrides}
