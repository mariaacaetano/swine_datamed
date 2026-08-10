import { useEffect, useMemo, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { Mic, Send, X } from "lucide-react"
import sintomasCsv from "../../../base_data/SintomasDoencas.csv?raw"
import variaveisCsv from "../../../base_data/BaseVariaveis.csv?raw"
import doencasCsv from "../../../base_data/BaseDoencas.csv?raw"
import farmacosCsv from "../../../base_data/BularioFarmacos.csv?raw"
import "./FloatingCompass.css"

const hiddenRoutes = new Set(["/login", "/cadastro", "/recuperar-senha"])
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

function isFilled(value) {
  return !emptyValues.has(normalize(value).trim())
}

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

function buildData() {
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
        indications &&
        diseases.some((disease) => indications.includes(normalize(disease.name))) ||
        splitList(farmaco["Indicações principais"]).some((item) => haystack.includes(normalize(item)))
      )
    })
    .slice(0, 3)
}

function makeReply(text, data) {
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

function FloatingCompass() {
  const { pathname } = useLocation()
  const data = useMemo(() => buildData(), [])
  const recognitionRef = useRef(null)
  const listeningRef = useRef(false)
  const wakeEnabledRef = useRef(false)
  const openRef = useRef(false)
  const restartTimerRef = useRef(0)
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState("")
  const [listening, setListening] = useState(false)
  const [wakeEnabled, setWakeEnabled] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: 'Fale ou digite os sinais observados. Você também pode dizer "ei, datamed" para abrir este painel.',
    },
  ])

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

  const submit = () => {
    const text = input.trim()
    if (!text) return

    setMessages((current) => [
      ...current,
      { role: "user", text },
      { role: "assistant", text: makeReply(text, data) },
    ])
    setInput("")
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

          <div className="floating-compass__messages">
            {messages.map((message, index) => (
              <p className={`floating-compass__message floating-compass__message--${message.role}`} key={`${message.role}-${index}`}>
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
