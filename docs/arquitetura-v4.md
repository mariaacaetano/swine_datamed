# Pipeline de triagem e arquitetura v4

O sistema mantém React/Vite e Django/DRF em um monólito modular. A API valida a
entrada; o serviço `bulario.triage` coordena extração, inferência e consulta ao
bulário. Os motores aceitam `inferir_caso(caso)` e preservam `inferir(texto)` para
os experimentos existentes. O painel comparativo e sua API estão preservados na
branch `engines`; a branch principal `main` mantém o fluxo de triagem.

## Escolha das três etapas

| Etapa | Implementação adotada | Fundamentação |
|---|---|---|
| Leitura de entrada | Extrator clínico compartilhado, padrões, sinônimos e estados de observação | Todos os oito motores já compartilhavam esse extrator. Cobertura 1,0 nos textos sintéticos não demonstra superioridade sobre outro extrator nem compreensão geral. |
| Inferência de doenças | Bernoulli Naive Bayes supervisionado (`machine_learning`) como padrão | Melhor resultado no ensaio de estados: acurácia@1 0,7400 e recuperação@5 0,9567, em 300 observações simuladas. No ensaio somente positivo, Bayes manual foi superior: 0,8710 contra 0,8516. A escolha privilegia a entrada parcial da conversa. |
| Consulta de fármacos | Relações `Indicacao` e `Farmaco`, por hipótese e prioridade cadastrada | Os relatórios existentes não avaliam seleção terapêutica. É uma decisão arquitetural auditável, sem alegação de vitória experimental. |

Resultados de origem: `machine/artifacts/classification_metrics_v3.json` e
`machine/artifacts_states/classification_metrics_v3.json`. Os protocolos possuem
tamanhos e entradas diferentes; nenhuma dessas métricas comprova desempenho
clínico. Os demais motores continuam disponíveis para experimentação.

Os fármacos são associados às hipóteses, com doença, indicação, tipo e prioridade
na resposta. A ordenação usa primeiro a posição da hipótese e depois a prioridade
numérica cadastrada. Não compara numericamente scores de motores diferentes.
Não há cálculo de dose, prescrição ou verificação automática de contraindicações.

## Conversa em várias rodadas

`POST /api/triagem/` aceita `texto`, `contexto_clinico`, `pergunta_anterior`,
`perguntas_realizadas`, `dados_clinicos` e, para experimentação, `mecanismo`.
A resposta devolve o contexto atualizado, pergunta seguinte, perguntas já feitas,
hipóteses, evidências, fármacos associados, identificação das etapas e versões.

```json
{
  "texto": "Leitoa com tosse há dois dias",
  "dados_clinicos": {
    "temperatura_corporal_c": 40.2,
    "temperatura_ambiente_c": 32,
    "idade_dias": 60,
    "fase_reprodutiva": "Creche",
    "tipo_suino": "Leitoa",
    "peso_kg": 18,
    "animais_afetados": 3
  }
}
```

O cliente envia os campos de conversa devolvidos na resposta anterior. Respostas
curtas como `40,2`, `2 meses`, `2 dias`, `sim`, `não` e `não sei` são interpretadas
no contexto da pergunta. Perguntas já feitas não se repetem automaticamente.
Novas observações e correções continuam aceitas após a coleta dos campos.
As últimas menções atualizam os fatos; omissões não apagam informações anteriores.
Temperatura ambiente não é convertida em temperatura corporal ou febre.

O classificador atual utiliza sintomas e os campos clínicos previstos no artefato
(temperatura corporal, idade, sexo, fase, estado reprodutivo e duração).
Temperatura ambiente, tipo de suíno, peso e quantidade de animais ficam registrados
como contexto; não se inventam coeficientes ou evidências clínicas para esses
campos. Tipos que também descrevem fase podem ser reconhecidos como fase.
Idades em semanas, meses e anos são convertidas aproximadamente para dias
(7, 30 e 365 dias, respectivamente).

A conversa permanece no navegador: `localStorage` separado pelo identificador
do usuário autenticado; `sessionStorage` para visitantes. O histórico antigo
global não é migrado automaticamente entre contas. Não há sincronização entre
dispositivos. O hook `useTriage` é compartilhado pelo chat e painel flutuante,
impede envios simultâneos na mesma conversa e cancela chamadas ao desmontar.

## Dados, artefatos e operação

- `GET /api/catalogo/` é a fonte do catálogo para o React; os CSVs ficam na importação.
- `GET /api/pipeline/` fornece os motores, disponibilidade, modelo e schema reais.
- `GET /api/machine-learning/status/` verifica o artefato efetivo, não apenas um JSON de métricas.
- A triagem retorna 503 se o modelo selecionado estiver ausente ou incompatível; não troca silenciosamente de algoritmo.
- Novos datasets levam o hash semântico da base. O treino registra hashes dos CSVs e publica o artefato com substituição atômica.
- Artefatos históricos sem hash da base continuam identificados com versão de origem desconhecida. Um hash conhecido divergente bloqueia a triagem até o retreino.
- A reimportação reconcilia as relações doença–sintoma com a união das duas tabelas de origem, removendo associações obsoletas dessas doenças.
- Suínos, medicações e casos clínicos usam paginação de 50 registros, máximo de 200 por página. O cliente atual agrega páginas para preservar os painéis existentes.
- A listagem de suínos reaproveita medicações pré-carregadas, mantendo constante o número de consultas.

`GET /api/preparacao-dados/` continua informativo. A preparação pesada é feita
exclusivamente por comandos administrativos; POST anônimo é recusado, e POST
administrativo retorna 405 com a orientação do comando. Não há fila de tarefas
ou serviço adicional exigido para executar o projeto.

```bash
./venv/bin/python config/manage.py import_swine_data --generate
```

Não execute esse comando em uma base em uso sem planejar a atualização dos
datasets e dos modelos: geração e treinamento são operações administrativas.
Os arquivos históricos não são retreinados automaticamente nesta alteração.

## Configuração e verificação

As variáveis do backend devem ser exportadas no processo que inicia o Django.
O Vite lê suas próprias variáveis `.env`; o Django não carrega esse arquivo
automaticamente. `MYSQL_DATABASE` ausente seleciona SQLite.

Em desenvolvimento, `DJANGO_DEBUG=true` permite uma chave efêmera se nenhuma
for configurada. Para sessões persistentes entre reinícios, defina uma chave.
Em produção, use `DJANGO_DEBUG=false`, uma `DJANGO_SECRET_KEY` forte e estável,
hosts e origens explícitos. HTTPS, cookies seguros e HSTS ficam habilitados
por padrão nesse modo. A terminação TLS deve corresponder à implantação real.

```bash
./venv/bin/python config/manage.py test --noinput
npm test
npm run lint
npm run build
```

O runner descobre os aplicativos mesmo quando chamado na raiz. A integração
contínua executa essas verificações com banco temporário. O teste de navegador
requer frontend e backend ativos e Chrome disponível:

```bash
npm run test:browser
```

Ele usa perfil descartável, verifica múltiplas rodadas, correções, formulário
clínico, isolamento do histórico e painel flutuante. A captura móvel fica em
`/tmp/swine-chat-mobile.png`; `SWINE_URL`, `CHROME_BINARY` e `SWINE_SCREENSHOT`
permitem ajustar o ambiente. A entrada clínica nos testes não é persistida no
backend.
