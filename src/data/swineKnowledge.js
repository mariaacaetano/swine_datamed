import sintomasCsv from "../../base_data/SintomasDoencas.csv?raw"
import variaveisCsv from "../../base_data/BaseVariaveis.csv?raw"
import doencasCsv from "../../base_data/BaseDoencas.csv?raw"
import farmacosCsv from "../../base_data/BularioFarmacos.csv?raw"

const emptyValues = new Set(["", "—", "-", "completar"])

export function parseCsv(text) {
  const rows = []
  let cell = ""
  let row = []
  let quoted = false

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    const next = text[i + 1]

    if (char === '"' && quoted && next === '"') {
      cell += '"'
      i += 1
    } else if (char === '"') {
      quoted = !quoted
    } else if (char === "," && !quoted) {
      row.push(cell.trim())
      cell = ""
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1
      row.push(cell.trim())
      if (row.some(Boolean)) rows.push(row)
      row = []
      cell = ""
    } else {
      cell += char
    }
  }

  if (cell || row.length) {
    row.push(cell.trim())
    if (row.some(Boolean)) rows.push(row)
  }

  const headerIndex = rows.findIndex(
    (candidate) => candidate.filter((value) => value.trim()).length > 1
  )
  if (headerIndex === -1) return []

  const headers = rows[headerIndex]
  const data = rows.slice(headerIndex + 1)
  return data.map((values) =>
    headers.reduce((acc, header, index) => {
      acc[header] = values[index] || ""
      return acc
    }, {})
  )
}

export function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
}

function isFilled(value) {
  return !emptyValues.has(normalize(value).trim())
}

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function buildData() {
  const sintomas = parseCsv(sintomasCsv)
  const doencas = parseCsv(doencasCsv)
  const variaveis = parseCsv(variaveisCsv)
  const farmacos = parseCsv(farmacosCsv).filter((farmaco) => {
    const usefulFields = [
      farmaco["Princípio ativo"],
      farmaco.Classe,
      farmaco["Indicações principais"],
      farmaco.Posologia,
      farmaco["Via administração"],
      farmaco.Carência,
    ]
    return isFilled(farmaco["Nome comercial"]) && usefulFields.filter(isFilled).length >= 3
  })

  return { sintomas, doencas, variaveis, farmacos }
}

function scoreDiseases(text, sintomas, doencas) {
  const normalizedText = normalize(text)
  const scores = new Map()
  const matchedSymptoms = []

  sintomas.forEach((row) => {
    const symptom = row.SINTOMA
    if (symptom && normalizedText.includes(normalize(symptom))) {
      matchedSymptoms.push(symptom)
      splitList(row["DOENÇAS ASSOCIADAS"]).forEach((disease) => {
        scores.set(disease, (scores.get(disease) || 0) + 2)
      })
    }
  })

  doencas.forEach((row) => {
    splitList(row.SINTOMAS).forEach((symptom) => {
      if (symptom && normalizedText.includes(normalize(symptom))) {
        matchedSymptoms.push(symptom)
        scores.set(row["DOENÇA"], (scores.get(row["DOENÇA"]) || 0) + 1)
      }
    })
  })

  const ranked = [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([name, score]) => {
      const detail = doencas.find((row) => normalize(row["DOENÇA"]) === normalize(name))
      return { name, score, type: detail?.TIPO, phase: detail?.["FASE COMUM"] }
    })

  return { ranked, matchedSymptoms: [...new Set(matchedSymptoms)].slice(0, 8) }
}

function findFarmacos(text, diseases, farmacos) {
  const haystack = normalize([text, ...diseases.map((disease) => disease.name)].join(" "))
  return farmacos
    .filter((farmaco) => {
      const indications = normalize(farmaco["Indicações principais"])
      return (
        (indications && diseases.some((disease) => indications.includes(normalize(disease.name)))) ||
        splitList(farmaco["Indicações principais"]).some((item) => haystack.includes(normalize(item)))
      )
    })
    .slice(0, 3)
}

export function makeReply(text, data) {
  const { ranked, matchedSymptoms } = scoreDiseases(text, data.sintomas, data.doencas)
  const farmacos = findFarmacos(text, ranked, data.farmacos)
  const variables = data.variaveis.slice(0, 5).map((item) => item["Variável"])

  if (!text.trim()) {
    return "Me diga os sinais observados no animal ou lote. Exemplo: febre alta, tosse, diarreia, apatia, idade e fase produtiva."
  }

  if (!ranked.length) {
    return `Ainda não encontrei uma hipótese forte com os sintomas informados. Para melhorar a triagem, informe: ${variables.join(", ")}.`
  }

  const hypotheses = ranked
    .map((disease, index) => `${index + 1}. ${disease.name}${disease.phase ? ` (${disease.phase})` : ""}`)
    .join("\n")

  const meds = farmacos.length
    ? `\n\nFármacos na base com informação relacionada:\n${farmacos
        .map((farmaco) => `- ${farmaco["Nome comercial"]}: ${farmaco["Princípio ativo"]}. Via: ${farmaco["Via administração"] || "não informada"}. Carência: ${farmaco.Carência || "não informada"}.`)
        .join("\n")}`
    : "\n\nNão encontrei fármacos suficientemente preenchidos relacionados a essas hipóteses na base atual."

  const symptoms = matchedSymptoms.length
    ? `Sintomas reconhecidos: ${matchedSymptoms.join(", ")}.\n\n`
    : ""

  return `${symptoms}Hipóteses de apoio para triagem:\n${hypotheses}\n\nPerguntas importantes: temperatura corporal, idade/fase produtiva, quantidade de animais afetados, evolução em horas/dias, mortalidade e tratamentos já usados.${meds}\n\nAtenção: isso é apoio à triagem e não substitui avaliação de médico-veterinário.`
}
