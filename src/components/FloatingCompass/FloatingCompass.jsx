import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { Mic, Send, X } from "lucide-react"
import InferenceModelSwitch from "../InferenceModelSwitch/InferenceModelSwitch"
import { useInferenceModel } from "../InferenceModelSwitch/useInferenceModel"
import { useTriage, createConversation } from "../../hooks/useTriage"
import { useAuthScope } from "../../hooks/useAuthScope"
import ClinicalContext from "../ClinicalContext/ClinicalContext"
import { createVoiceRecognition } from "./voiceRecognition"
import "./FloatingCompass.css"

const hiddenRoutes = new Set(["/login", "/cadastro", "/recuperar-senha"])
const voicePreferenceKey = "swine-voice-enabled"

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
  const scope = useAuthScope()
  return <FloatingConversation key={scope} />
}

function FloatingConversation() {
  const [inferenceModel, setInferenceModel] = useInferenceModel()
  const { pathname } = useLocation()
  const voiceRef = useRef(null)
  const openRef = useRef(false)
  const wakeResultRef = useRef(-1)
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState("")
  const [voiceState, setVoiceState] = useState({ status: "idle", enabled: false, error: "" })
  const [conversation, setConversation] = useState(createConversation)
  const messages = conversation.messages
  const chatStarted = messages.some((message) => message.role === "user")
  const activeInferenceModel = conversation.inferenceModel || inferenceModel
  const updateConversation = (updater) => setConversation((current) => ({ ...updater(current), updatedAt: new Date().toISOString() }))
  const setMessages = (updater) => setConversation((current) => ({ ...current, messages: updater(current.messages) }))
  const { send, busy } = useTriage(conversation, updateConversation, activeInferenceModel)

  const shouldHide = hiddenRoutes.has(pathname)
  const listening = voiceState.status === "listening"
  const wakeEnabled = voiceState.enabled

  useEffect(() => {
    openRef.current = open
  }, [open])

  useEffect(() => {
    if (shouldHide) return undefined

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return undefined

    const voice = createVoiceRecognition(SpeechRecognition, {
      onState: (state) => {
        setVoiceState(state)
        if (state.status === "starting") wakeResultRef.current = -1
        if (state.error) setOpen(true)
      },
      onResult: (event) => {
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index]
          const transcript = result[0]?.transcript?.trim()
          if (!transcript) continue

          if (Array.from(result).some((alternative) => isWakePhrase(alternative.transcript))) {
            if (wakeResultRef.current !== index) {
              wakeResultRef.current = index
              if (!openRef.current) {
                openRef.current = true
                setOpen(true)
                setMessages((current) => [
                  ...current,
                  { role: "assistant", text: "Estou ouvindo. Me conte os sintomas do animal ou lote." },
                ])
              }
            }
            continue
          }

          if (result.isFinal && openRef.current && wakeResultRef.current !== index) {
            setInput((current) => `${current} ${transcript}`.trim())
          }
        }
      },
    })
    voiceRef.current = voice
    let disposed = false
    let microphonePermission
    const syncPermission = () => {
      if (disposed) return
      if (microphonePermission.state === "granted" && localStorage.getItem(voicePreferenceKey) !== "off") {
        voice.start()
      } else {
        voice.stop()
      }
    }

    if (window.isSecureContext && navigator.permissions?.query) {
      navigator.permissions.query({ name: "microphone" }).then((permission) => {
        if (disposed) return
        microphonePermission = permission
        permission.addEventListener("change", syncPermission)
        syncPermission()
      }).catch(() => {
        // Browsers without microphone permission queries still support manual activation.
      })
    }

    return () => {
      disposed = true
      microphonePermission?.removeEventListener("change", syncPermission)
      voice.dispose()
      voiceRef.current = null
    }
  }, [shouldHide])

  if (shouldHide) return null

  const submit = async () => {
    const text = input.trim()
    if (!text || busy) return
    setInput("")
    await send(text)
  }

  const startListening = ({ enableWake = false, openPanel = false } = {}) => {
    const voice = voiceRef.current
    if (!voice || !window.isSecureContext) {
      setVoiceState({
        status: "error",
        enabled: false,
        error: !window.isSecureContext
          ? "Para usar o microfone, abra o site por HTTPS ou localhost. Você pode digitar os sintomas."
          : "Reconhecimento de voz não disponível neste navegador. Você pode digitar os sintomas.",
      })
      setOpen(true)
      return
    }

    if (openPanel) {
      openRef.current = true
      setOpen(true)
    }
    if (enableWake) {
      localStorage.setItem(voicePreferenceKey, "on")
      voice.start()
    }
  }

  const stopListening = () => {
    localStorage.setItem(voicePreferenceKey, "off")
    voiceRef.current?.stop()
  }

  const toggleListening = () => {
    if (wakeEnabled) {
      stopListening()
    } else {
      startListening({ enableWake: true, openPanel: true })
    }
  }

  const closePanel = () => {
    openRef.current = false
    setOpen(false)
    voiceRef.current?.restart()
  }

  const handleMainButton = () => {
    if (openRef.current) {
      closePanel()
      return
    }

    startListening({ enableWake: true, openPanel: true })
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
            <button type="button" onClick={closePanel} aria-label="Fechar chat">
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

          <ClinicalContext onSubmit={send} disabled={busy} result={conversation.result} />
          <footer>
            <p className="floating-compass__voice-status" role="status">
              {voiceState.error || (listening
                ? "Microfone ativo. Estou ouvindo."
                : wakeEnabled ? "Iniciando escuta..." : "Clique no microfone para ativar a voz.")}
            </p>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Descreva sintomas, idade, fase e evolução..."
              rows={3}
            />
            <div>
              <button type="button" className={listening ? "is-listening" : ""} onClick={toggleListening} aria-label={wakeEnabled ? "Desativar voz" : "Ativar voz"} aria-pressed={wakeEnabled}>
                <Mic size={18} />
              </button>
              <button type="button" disabled={busy || !input.trim()} onClick={submit} aria-label="Enviar dados da triagem">
                <Send size={18} />
              </button>
            </div>
          </footer>
        </section>
      )}

      {!open && (
        <span className="floating-compass__hint" role="status">
          {listening ? 'Diga "ei, datamed"' : wakeEnabled ? "Iniciando escuta..." : 'Clique para ativar "ei, datamed"'}
        </span>
      )}

      <button
        className={`floating-compass__button ${listening ? "is-awake" : ""}`}
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
