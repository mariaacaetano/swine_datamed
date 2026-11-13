import { useEffect, useRef } from "react"
import { inferir } from "../services/inferencia"

export const initialMessage = {
  role: "assistant",
  text: "Conte o que está acontecendo com o animal ou lote. Você pode começar pelos sinais, idade, fase, tipo de suíno ou temperatura corporal e do ambiente. Vou organizar os dados e fazer perguntas ao longo da triagem.",
}

export function createConversation(title = "Nova triagem") {
  const now = new Date().toISOString()
  return { id: crypto.randomUUID(), title, createdAt: now, updatedAt: now, messages: [initialMessage] }
}

export function useTriage(conversation, updateConversation, model = "machine_learning") {
  const requests = useRef(new Map())
  useEffect(() => {
    const current = requests.current
    return () => { current.forEach((controller) => controller.abort()); current.clear() }
  }, [])
  const busy = conversation.messages.some((message) => message.pending)
  const send = async (text, clinicalData = {}) => {
    const content = text.trim()
    if ((!content && !Object.keys(clinicalData).length) || requests.current.has(conversation.id)) return false
    const controller = new AbortController()
    requests.current.set(conversation.id, controller)
    const pendingId = crypto.randomUUID()
    updateConversation((current) => ({
      ...current, inferenceModel: current.inferenceModel || model,
      title: current.title === "Nova triagem" ? content.slice(0, 42) || "Dados do animal" : current.title,
      messages: [...current.messages, { role: "user", text: content || "Atualizei os dados do animal." },
        { id: pendingId, role: "assistant", pending: true, text: "Analisando o caso..." }],
    }))
    try {
      const result = await inferir(content, conversation.inferenceModel || model, {
        context: conversation.clinicalContext || "", question: conversation.question,
        askedQuestions: conversation.askedQuestions, clinicalData,
      }, { signal: controller.signal })
      if (controller.signal.aborted) return false
      updateConversation((current) => ({
        ...current, clinicalContext: result.contexto_clinico, question: result.pergunta_complementar,
        askedQuestions: result.perguntas_realizadas, result,
        messages: current.messages.map((message) => message.id === pendingId
          ? { id: pendingId, role: "assistant", text: result.resposta } : message),
      }))
    } catch (error) {
      if (controller.signal.aborted) return false
      updateConversation((current) => ({
        ...current, messages: current.messages.map((message) => message.id === pendingId
          ? { id: pendingId, role: "assistant", text: `Não foi possível atualizar a triagem: ${error.message}` } : message),
      }))
    } finally {
      requests.current.delete(conversation.id)
    }
    return true
  }
  return { send, busy }
}
