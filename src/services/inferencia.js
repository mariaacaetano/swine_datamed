import { requestJson } from "./api"

export function inferir(texto, mecanismo = "machine_learning", conversation = {}, options = {}) {
  return requestJson("/triagem/", {
    method: "POST",
    signal: options.signal,
    body: JSON.stringify({
      texto,
      mecanismo,
      contexto_clinico: conversation.context || "",
      sintoma_perguntado: conversation.askedSymptom || "",
      pergunta_anterior: conversation.question || {},
      perguntas_realizadas: conversation.askedQuestions || [],
      dados_clinicos: conversation.clinicalData || {},
    }),
  })
}
