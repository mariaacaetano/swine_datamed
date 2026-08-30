# Swine DataMed

## Preparação da base clínica

O backend Django lê os seis arquivos de `base_data`, normaliza Unicode/acentuação,
espaços e listas, importa a base relacional e gera todas as combinações não vazias
de sintomas possíveis para cada doença.

```bash
./venv/bin/python config/manage.py migrate
./venv/bin/python config/manage.py import_swine_data --clear --generate
```

O primeiro resultado contém 2.084 combinações únicas e 80 colunas binárias de sintomas,
gravadas em `generated_data/dataset_combinacoes_sintomas.csv`. Um segundo conjunto
com 10 observações controladas por combinação contém 20.840 linhas, 52 variáveis
clínicas discretizadas e ausências explícitas como `Não informado`; ele é gravado em
`generated_data/dataset_clinico_ampliado.csv`. Ambos utilizam UTF-8 BOM,
para abertura correta no Excel, e também nas tabelas `GeracaoDataset` e
`CasoClinico`. O comando aceita `--total`, `--variations`, `--output` e
`--clinical-output`.

Um terceiro conjunto, específico para aprendizado de máquina, é gerado em
`generated_data/machine_learning/`. Com 100 variações por combinação, possui
208.400 registros divididos por combinação-base antes da expansão: 146.400 para
treino, 31.000 para validação e 31.000 para teste. Os arquivos
`treino.csv`, `validacao.csv` e `teste.csv` não contêm campos que revelem
diretamente o diagnóstico; `metadados.json` registra a divisão e a semente.
O comando aceita também `--ml-variations` e `--ml-output`.

A seção correspondente da API é:

- `GET /api/preparacao-dados/`: contagens e última geração;
- `POST /api/preparacao-dados/`: importa e gera (`total`, `variacoes`, `semente`, `limpar`);
- `GET /api/casos-clinicos/?geracao=<id>`: consulta os casos;
- `GET /api/vacinas/`: consulta as vacinas importadas.

## Mecanismos de inferência

Os mecanismos são executados exclusivamente no backend e compartilham a base
importada de `base_data`:

- `config/regras/`: cobertura determinística das relações doença-sintoma;
- `config/semantica/`: travessia do grafo Sintoma → Doença → Fármaco;
- `config/machine/`: modelos supervisionados sobre as combinações de sintomas,
  com seleção pelo F1-macro de validação e persistência do modelo vencedor.

Cada mecanismo possui um endpoint próprio (`/api/regras/inferir/`,
`/api/semantica/inferir/` e `/api/machine-learning/inferir/`). O endpoint
`POST /api/triagem/` recebe `texto` e, opcionalmente, `mecanismo`; o padrão é
`regras`. O frontend não executa inferência nem lê a base clínica para triar.

### Treinamento de machine learning

Após gerar `treino.csv`, `validacao.csv` e `teste.csv`, execute:

```bash
./venv/bin/python config/manage.py train_ml
```

Versões com valores diferentes de `k` podem coexistir usando diretórios próprios.
Por exemplo, para gerar e treinar a variante `k=10` sem substituir a versão atual:

```bash
./venv/bin/python config/manage.py generate_ml_dataset --k 10 --output generated_data/machine_learning_k10
./venv/bin/python config/manage.py train_ml --data-dir generated_data/machine_learning_k10 --artifact-dir config/machine/artifacts_k10
```

O comando ajusta o pré-processamento somente no treino, compara Bernoulli Naive
Bayes, regressão logística por SGD, árvore de decisão e Random Forest pela macro-F1
de validação, reajusta o vencedor com treino+validação e avalia uma única vez no
teste. O modelo fica em `config/machine/artifacts/model.joblib` e as métricas em
`config/machine/artifacts/metrics.json`. Para comparar regras, grafo, ML, Rede
Bayesiana e Lógica Fuzzy no mesmo conjunto de teste, execute:

```bash
./venv/bin/python config/manage.py evaluate_all_models
```

As métricas comparativas são gravadas em
`config/machine/artifacts/comparative_metrics.json`. A API expõe o estado em
`GET /api/machine-learning/status/`.

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
