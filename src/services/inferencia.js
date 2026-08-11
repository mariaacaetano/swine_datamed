import { requestJson } from "./auth"

export function inferir(texto, mecanismo = "regras", conversation = {}) {
  return requestJson("/triagem/", {
    method: "POST",
    body: JSON.stringify({
      texto,
      mecanismo,
      contexto_clinico: conversation.context || "",
      sintoma_perguntado: conversation.askedSymptom || "",
    }),
  })
}

export function compararInferencias(texto) {
  return requestJson("/comparacao-inferencia/", {
    method: "POST",
    body: JSON.stringify({ texto }),
  })
}
