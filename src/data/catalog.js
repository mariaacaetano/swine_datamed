import { useEffect, useState } from "react"
import { requestJson } from "../services/api"

export function normalize(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
}

export function medicationForDisplay(item) {
  return {
    id: item.id, "Nome comercial": item.nome_comercial, "Princípio ativo": item.principio_ativo,
    Classe: item.classe, "Indicações principais": item.indicacoes_principais, Posologia: item.posologia,
    "Via administração": item.via_administracao, Carência: item.carencia,
    Contraindicações: item.contraindicacoes, "Reações adversas": item.reacoes_adversas,
    "Mecanismo de ação": item.mecanismo_acao, Precauções: item.precaucoes,
  }
}

const emptyCatalog = { farmacos: [], sintomas: [], doencas: [], variaveis: [] }

export function useCatalog() {
  const [state, setState] = useState({ data: emptyCatalog, loading: true, error: "" })
  useEffect(() => {
    const controller = new AbortController()
    requestJson("/catalogo/", { signal: controller.signal }).then((catalog) => {
      setState({ data: { ...catalog, farmacos: catalog.farmacos.map(medicationForDisplay) }, loading: false, error: "" })
    }).catch((error) => {
      if (!controller.signal.aborted) setState({ data: emptyCatalog, loading: false, error: error.message })
    })
    return () => controller.abort()
  }, [])
  return state
}
