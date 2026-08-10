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
`generated_data/machine_learning/`. Com 96 variações por combinação, possui
200.064 registros divididos por combinação-base antes da expansão. Os arquivos
`treino.csv`, `validacao.csv` e `teste.csv` não contêm campos que revelem
diretamente o diagnóstico; `metadados.json` registra a divisão e a semente.
O comando aceita também `--ml-variations` e `--ml-output`.

A seção correspondente da API é:

- `GET /api/preparacao-dados/`: contagens e última geração;
- `POST /api/preparacao-dados/`: importa e gera (`total`, `variacoes`, `semente`, `limpar`);
- `GET /api/casos-clinicos/?geracao=<id>`: consulta os casos;
- `GET /api/vacinas/`: consulta as vacinas importadas.

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
