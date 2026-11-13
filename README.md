# Swine DataMed

## Arquitetura e chat atuais (v4)

O fluxo padrão usa extração clínica compartilhada → Naive Bayes supervisionado
→ consulta relacional das indicações farmacológicas. O chat aceita várias rodadas,
correções e campos estruturados do animal e do ambiente. Consulte
[a arquitetura v4, a escolha dos motores e os limites dos ensaios](docs/arquitetura-v4.md).

## Execução local

Em terminais separados, execute:

```bash
npm run dev
./venv/bin/python config/manage.py runserver
```

O frontend usa `http://localhost:5174` e conecta à API em
`http://localhost:8001/api`. O backend usa a porta 8001 por padrão.
Para alterar o endereço da API, configure `VITE_API_BASE_URL` no arquivo `.env`.

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
- A importação e a geração são executadas pelo comando administrativo; POST nessa rota não executa preparação;
- `GET /api/casos-clinicos/?geracao=<id>`: consulta os casos;
- `GET /api/vacinas/`: consulta as vacinas importadas.

## Mecanismos de inferência

Os mecanismos são executados exclusivamente no backend e compartilham a base
importada de `base_data`:

- `config/regras/`: motor heurístico e motor simbólico por encadeamento progressivo;
- `config/semantica/`: consulta às arestas diretas Sintoma → Doença, seguida de ranking por Jaccard e ajuste clínico; fármacos são consultados posteriormente;
- `config/machine/`: modelos supervisionados sobre as combinações de sintomas,
  com seleção pelo F1-macro de validação e persistência do modelo vencedor.
- `config/bulario/knowledge_engines.py`: Naive Bayes com parâmetros manuais,
  Sugeno de ordem zero e composição max–min de Sanchez como motores separados.

Cada mecanismo possui um endpoint próprio (`/api/regras/inferir/`,
`/api/semantica/inferir/` e `/api/machine-learning/inferir/`). O endpoint
`POST /api/triagem/` recebe `texto` e, opcionalmente, `mecanismo`; o padrão é
`machine_learning` na arquitetura v4. O frontend consulta o catálogo pela API.

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
`config/machine/artifacts/comparative_metrics_v3.json`. A API expõe o estado em
`GET /api/machine-learning/status/`.

Para avaliar a versão atual dos oito motores, limitada à conversão e
classificação, sem consultar indicações terapêuticas, execute:

```bash
./venv/bin/python config/manage.py evaluate_classification
```

O comando usa `generated_data/machine_learning_k10/teste.csv`, preserva os nomes
compostos dos sintomas e grava contadores, métricas micro, cobertura da conversão
e tempo por entrada distinta em `config/machine/artifacts/classification_metrics_v3.json`.
As variáveis clínicas do CSV não são fornecidas aos modelos nesse protocolo.

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

### Dois motores baseados em regras

`MotorRegras` mantém a seleção de candidatas e a pontuação heurística de cobertura, precisão e ajuste clínico. Os pesos são constantes de implementação sem calibração clínica documentada.

`MotorRegrasEncadeadas` (`config/regras/chaining.py`) deriva fatos por encadeamento progressivo: evidência → candidata → admissível → suporte → hipótese. As regras E1–E8 são explícitas, disparam uma vez por enfermidade e encerram no ponto fixo. A restrição gestacional para macho bloqueia a candidata. Negar um sintoma associado não exclui a doença, pois associação não implica obrigatoriedade; divergência de fase deriva uma categoria restrita. Sintomas não mencionados não são negações; sintomas incertos não são tratados como confirmados. A saída contém `trilha_inferencia`, inclusive os bloqueios, e categorias ordinais sem probabilidades. As regras ainda não possuem validação clínica específica.

O motor está disponível na seleção da conversa, no painel comparativo, em `/api/regras/encadeadas/inferir/` e em `/api/triagem/` com `mecanismo: "regras_encadeadas"`. O comando `evaluate_all_models` inclui ambos os motores em novas execuções; métricas anteriores não avaliam o motor novo.


## Inferência corrigida (v2, registro histórico)

Esta seção descreve a revisão anterior. A implementação atual é apresentada
na seção v3 e em [docs/inferencia-v3.md](docs/inferencia-v3.md).

A conversão separa sinais confirmados, negados e incertos, aplica negação aos
sinônimos e usa a última menção de cada sinal na conversa. Temperatura exige
unidade ou contexto explícito; idade em dias não vira temperatura nem duração.

O motor `rede_bayesiana` agora implementa Naive Bayes em estrela: prior uniforme,
P(sinal presente | doença) = 0,8 quando associado e 0,2 quando não associado,
com probabilidades complementares para a ausência explícita. Compara a mesma
evidência em todas as doenças e marginaliza os sinais desconhecidos/incertos.
As CPTs são manuais e experimentais, não estimadas de dados clínicos.

O motor `fuzzy` executa Sugeno de ordem zero sobre cobertura e precisão graduadas,
com pertinências triangulares, nove regras explícitas, AND produto e média
ponderada dos consequentes. A certeza da observação incerta recebe peso 0,5;
esse peso não é uma probabilidade. A temperatura utiliza rampas contínuas para
febre, substituindo o bônus aditivo anterior. Saídas sem suporte são omitidas.

O ML carrega o nome real do artefato (atualmente Random Forest em k=10 e
Bernoulli Naive Bayes em k=100). No Bernoulli treinado, a inferência parcial
marginaliza atributos não observados e usa ausências explícitas diretamente,
sem penalidade posterior arbitrária. O Random Forest existente continua com
a representação binária do treinamento; desconhecido e ausência têm a mesma
codificação zero, limitação informada na saída. Idades numéricas são convertidas
nas faixas do treinamento. As métricas embutidas nos artefatos descrevem o
protocolo histórico de vetores completos, não a inferência parcial atual.

A interface identifica o significado de cada score e não transforma pontuações
em confiança clínica ou adequação terapêutica. Os comandos de avaliação usam
os motores reais e a mesma implementação de contagem; incluem o encadeamento,
preservam nomes compostos e contabilizam as listas efetivamente retornadas.

Os arquivos de métricas anteriores e os números do TCC representam a versão
histórica. Novas execuções geram arquivos `*_corrected.json` identificados pelo
protocolo `inferencia_corrigida_v2`; não substituem os resultados anteriores.
Veja [a descrição matemática e as limitações](docs/inferencia-v2.md).

## Inferência atual (v3)

Sanchez (`fuzzy_sanchez`) calcula a composição max–min paciente → sintoma → doença,
com trilha dos mínimos e contagem de empates. A relação sintoma–doença é binária
porque a base só contém vínculos; não foram inventados graus clínicos. Sugeno
permanece uma alternativa própria. Os oito motores estão na seleção da conversa
e no painel de comparação.

A extração preserva listas negadas/incertas, atributos negados, medições negadas
e a última correção de fase. Nomes de sintomas com hífen são preservados na
conversão do CSV e reconhecidos quando relatados com espaços.

O Random Forest atual representa sintomas presentes, ausentes, incertos e
desconhecidos em quatro categorias. O treinamento inclui contexto clínico omitido.
Para gerar as observações simuladas e treinar esse artefato separado:

```bash
./venv/bin/python config/manage.py generate_ml_observations
./venv/bin/python config/manage.py train_ml --data-dir generated_data/machine_learning_states --artifact-dir config/machine/artifacts_states --model random_forest
./venv/bin/python config/manage.py evaluate_classification
./venv/bin/python config/manage.py evaluate_classification --data generated_data/machine_learning_states/teste.csv --sample-size 300 --output config/machine/artifacts_states/classification_metrics_v3.json
./venv/bin/python config/manage.py evaluate_bayesian_sensitivity
./venv/bin/python config/manage.py audit_domain_base
```

As partições de origem são as existentes em `generated_data/machine_learning_k10`.
As colunas binárias de origem ficam disponíveis para auditoria e são excluídas
do treinamento e da inferência quando há colunas de estado. Os identificadores
de combinação-base não podem se repetir entre as partições. O artefato é
`config/machine/artifacts_states/model.joblib`; a chave legada `machine_learning_k10`
passa a carregá-lo. O artefato binário histórico em `artifacts_k10` é preservado.

As taxas de simulação e os parâmetros bayesianos continuam experimentais.
Somente as associações disponíveis não permitem estimar prevalência ou
probabilidades clínicas. O ensaio de sensibilidade compara a estabilidade de
nove configurações manuais, sem calibrá-las nem escolher uma como cenário real.
Os novos resultados usam `inferencia_corrigida_v3`, em arquivos próprios.

A auditoria identificou um marcador de informação faltante entre os 80 sintomas:
`Não informado no documento`, único vínculo de 32 doenças. Esse marcador é
preservado na origem e excluído da inferência e dos novos atributos de treino.
A base contém, portanto, 79 sinais e 80 doenças com perfis documentados; as 32
lacunas estão listadas em `config/bulario/domain_audit_v3.json`. O novo conjunto
tem 14.320 registros de treino, 3.100 de validação e 3.100 de teste. As classes
sem perfil são excluídas da saída do ML histórico, com renormalização sobre
as classes documentadas antes do limite de retorno.
