import sintomasCsv from "../../base_data/SintomasDoencas.csv?raw"
import variaveisCsv from "../../base_data/BaseVariaveis.csv?raw"
import doencasCsv from "../../base_data/BaseDoencas.csv?raw"
import farmacosCsv from "../../base_data/BularioFarmacos.csv?raw"

const emptyValues = new Set(["", "—", "-", "completar"])

function parseCsv(text) {
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
    } else if (char === '"') quoted = !quoted
    else if (char === "," && !quoted) {
      row.push(cell.trim())
      cell = ""
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1
      row.push(cell.trim())
      if (row.some(Boolean)) rows.push(row)
      row = []
      cell = ""
    } else cell += char
  }
  if (cell || row.length) {
    row.push(cell.trim())
    if (row.some(Boolean)) rows.push(row)
  }
  const headerIndex = rows.findIndex((candidate) => candidate.filter(Boolean).length > 1)
  if (headerIndex === -1) return []
  const headers = rows[headerIndex]
  return rows.slice(headerIndex + 1).map((values) =>
    headers.reduce((result, header, index) => {
      result[header] = values[index] || ""
      return result
    }, {})
  )
}

export function normalize(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
}

function isFilled(value) {
  return !emptyValues.has(normalize(value).trim())
}

export function buildData() {
  const farmacos = parseCsv(farmacosCsv).filter((farmaco) => {
    const fields = [farmaco["Princípio ativo"], farmaco.Classe, farmaco["Indicações principais"],
      farmaco.Posologia, farmaco["Via administração"], farmaco.Carência]
    return isFilled(farmaco["Nome comercial"]) && fields.filter(isFilled).length >= 3
  })
  return {
    sintomas: parseCsv(sintomasCsv),
    doencas: parseCsv(doencasCsv),
    variaveis: parseCsv(variaveisCsv),
    farmacos,
  }
}
