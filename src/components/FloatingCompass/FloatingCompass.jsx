import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { Mic, Send, X } from "lucide-react"
import InferenceModelSwitch from "../InferenceModelSwitch/InferenceModelSwitch"
import { useInferenceModel } from "../InferenceModelSwitch/useInferenceModel"
import { inferir } from "../../services/inferencia"
import "./FloatingCompass.css"

const hiddenRoutes = new Set(["/login", "/cadastro", "/recuperar-senha"])
const minimumThinkingTimeMs = 1200

function minimumThinkingTime() {
  return new Promise((resolve) => window.setTimeout(resolve, minimumThinkingTimeMs))
}

function createPendingMessage() {
  return {
    id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role: "assistant",
    text: "Pensando...",
    pending: true,
  }
}

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
}

function normalizeSpeech(value) {
  return normalize(value)
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ")
}

function isWakePhrase(value) {
  const compact = normalizeSpeech(value).replace(/\s/g, "")
  return ["eidatamed", "eaidatamed", "oidatamed", "heydatamed"].some((phrase) =>
    compact.includes(phrase)
  )
}

function FloatingCompass() {
  const [inferenceModel, setInferenceModel] = useInferenceModel()
  const { pathname } = useLocation()
  const recognitionRef = useRef(null)
  const listeningRef = useRef(false)
  const wakeEnabledRef = useRef(false)
  const openRef = useRef(false)
  const restartTimerRef = useRef(0)
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState("")
  const [listening, setListening] = useState(false)
  const [wakeEnabled, setWakeEnabled] = useState(false)
  const [conversationModel, setConversationModel] = useState("")
  const [clinicalContext, setClinicalContext] = useState("")
  const [askedSymptom, setAskedSymptom] = useState("")
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: 'Fale ou digite os sinais observados. Você também pode dizer "ei, datamed" para abrir este painel.',
    },
  ])
  const chatStarted = messages.some((message) => message.role === "user")
  const activeInferenceModel = conversationModel || inferenceModel

  const shouldHide = hiddenRoutes.has(pathname)

  useEffect(() => {
    openRef.current = open
  }, [open])

  useEffect(() => {
    wakeEnabledRef.current = wakeEnabled
  }, [wakeEnabled])

  useEffect(() => {
    listeningRef.current = listening
  }, [listening])

  useEffect(() => {
    if (shouldHide) return undefined

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return undefined

    const recognition = new SpeechRecognition()
    recognition.lang = "pt-BR"
    recognition.continuous = true
    recognition.interimResults = false

    const restartWakeListening = () => {
      window.clearTimeout(restartTimerRef.current)
      if (!wakeEnabledRef.current || shouldHide) return

      restartTimerRef.current = window.setTimeout(() => {
        try {
          recognition.start()
          setListening(true)
        } catch {
          setListening(false)
        }
      }, 450)
    }

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .slice(event.resultIndex)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim()

      if (!transcript) return

      if (isWakePhrase(transcript)) {
        setOpen(true)
        setWakeEnabled(true)
        setMessages((current) => [
          ...current,
          { role: "assistant", text: "Estou ouvindo. Me conte os sintomas do animal ou lote." },
        ])
        return
      }

      if (openRef.current) setInput((current) => `${current} ${transcript}`.trim())
    }

    recognition.onstart = () => setListening(true)
    recognition.onend = () => {
      setListening(false)
      restartWakeListening()
    }
    recognition.onerror = () => {
      setListening(false)
    }
    recognitionRef.current = recognition

    return () => {
      window.clearTimeout(restartTimerRef.current)
      recognition.stop()
      recognitionRef.current = null
    }
  }, [shouldHide])

  if (shouldHide) return null

  const submit = async () => {
    const text = input.trim()
    if (!text) return
    const selectedModel = activeInferenceModel
    const pendingMessage = createPendingMessage()

    setMessages((current) => [...current, { role: "user", text }, pendingMessage])
    setConversationModel(selectedModel)
    setInput("")
    try {
      const [resultado] = await Promise.all([
        inferir(text, selectedModel, { context: clinicalContext, askedSymptom }),
        minimumThinkingTime(),
      ])
      setClinicalContext(resultado.contexto_clinico)
      setAskedSymptom(resultado.pergunta_complementar?.sintoma || "")
      setMessages((current) => current.map((message) =>
        message.id === pendingMessage.id
          ? { role: "assistant", text: resultado.resposta }
          : message
      ))
    } catch (error) {
      setMessages((current) => current.map((message) =>
        message.id === pendingMessage.id
          ? { role: "assistant", text: `Não foi possível consultar o servidor: ${error.message}` }
          : message
      ))
    }
  }

  const startListening = ({ enableWake = false, openPanel = false } = {}) => {
    const recognition = recognitionRef.current
    if (!recognition) {
      setMessages((current) => [
        ...current,
        { role: "assistant", text: "Reconhecimento de voz não disponível neste navegador. Você pode digitar os sintomas." },
      ])
      setOpen(true)
      return
    }

    if (enableWake) {
      wakeEnabledRef.current = true
      setWakeEnabled(true)
    }

    if (openPanel) setOpen(true)

    try {
      recognition.start()
      setListening(true)
    } catch {
      setListening(listeningRef.current)
    }
  }

  const stopListening = () => {
    window.clearTimeout(restartTimerRef.current)
    wakeEnabledRef.current = false
    setWakeEnabled(false)
    recognitionRef.current?.stop()
    setListening(false)
  }

  const toggleListening = () => {
    if (listening) {
      stopListening()
    } else {
      startListening({ enableWake: true, openPanel: true })
    }
  }

  const handleMainButton = () => {
    if (open) {
      setOpen(false)
      return
    }

    startListening({ enableWake: true, openPanel: false })
  }

  return (
    <div className="floating-compass">
      {open && (
        <section className="floating-compass__panel" aria-label="Chat Swine Compass">
          <header>
            <img src="/logos/pig_logo.png" alt="" />
            <div>
              <strong>Swine Compass</strong>
              <span>Triagem assistida</span>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Fechar chat">
              <X size={18} />
            </button>
          </header>

          <div className="floating-compass__model">
            <InferenceModelSwitch
              value={activeInferenceModel}
              onChange={setInferenceModel}
              compact
              disabled={chatStarted}
            />
          </div>

          <div className="floating-compass__messages">
            {messages.map((message, index) => (
              <p
                className={`floating-compass__message floating-compass__message--${message.role} ${message.pending ? "floating-compass__message--pending" : ""}`}
                key={message.id || `${message.role}-${index}`}
              >
                {message.text}
              </p>
            ))}
          </div>

          <footer>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Descreva sintomas, idade, fase e evolução..."
              rows={3}
            />
            <div>
              <button type="button" className={listening ? "is-listening" : ""} onClick={toggleListening} aria-label="Ativar voz">
                <Mic size={18} />
              </button>
              <button type="button" onClick={submit} aria-label="Enviar sintomas">
                <Send size={18} />
              </button>
            </div>
          </footer>
        </section>
      )}

      {wakeEnabled && !open && (
        <span className="floating-compass__hint">
          {listening ? 'Diga "ei, datamed"' : "Clique para reativar"}
        </span>
      )}

      <button
        className={`floating-compass__button ${wakeEnabled ? "is-awake" : ""}`}
        type="button"
        onClick={handleMainButton}
        aria-label="Ativar Swine Compass por voz"
      >
        <img src="/logos/pig_logo.png" alt="" />
      </button>
    </div>
  )
}

export default FloatingCompass
