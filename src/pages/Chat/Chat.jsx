import { useEffect, useMemo, useRef, useState } from "react"
import { Bot, Check, Clock3, Mic, Pencil, Plus, Send, ShieldCheck, Sparkles, Trash2, UserRound, X } from "lucide-react"
import { buildData, makeReply } from "../../data/swineKnowledge"
import "./Chat.css"

const storageKey = "swine-datamed-chats"
const replyDelayMs = 2000
const initialMessage = {
  role: "assistant",
  text: "Olá, eu sou o Swine DataMed. Descreva os sintomas, fase produtiva, idade, temperatura e evolução do caso para eu organizar uma triagem assistida.",
}

function createPendingMessage() {
  return {
    id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role: "assistant",
    text: "Pensando...",
    pending: true,
  }
}

function createChat(title = "Nova triagem") {
  const now = new Date().toISOString()
  return {
    id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    title,
    createdAt: now,
    updatedAt: now,
    messages: [initialMessage],
  }
}

function loadChats() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "[]")
    return Array.isArray(saved) && saved.length ? saved : [createChat()]
  } catch {
    return [createChat()]
  }
}

function titleFromMessage(text) {
  return text.trim().slice(0, 42) || "Nova triagem"
}

function Chat() {
  const data = useMemo(() => buildData(), [])
  const initialChats = useMemo(() => loadChats(), [])
  const recognitionRef = useRef(null)
  const messagesRef = useRef(null)
  const replyTimeoutsRef = useRef([])
  const [chats, setChats] = useState(initialChats)
  const [activeChatId, setActiveChatId] = useState(initialChats[0]?.id)
  const [input, setInput] = useState("")
  const [listening, setListening] = useState(false)
  const [editingChatId, setEditingChatId] = useState("")
  const [editingTitle, setEditingTitle] = useState("")
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false)
  const activeChat = chats.find((chat) => chat.id === activeChatId) || chats[0]
  const messages = activeChat?.messages || [initialMessage]

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(chats))
  }, [chats])

  useEffect(() => {
    return () => {
      replyTimeoutsRef.current.forEach((timeoutId) => clearTimeout(timeoutId))
      replyTimeoutsRef.current = []
    }
  }, [])

  useEffect(() => {
    const list = messagesRef.current
    if (!list) return
    requestAnimationFrame(() => {
      list.scrollTop = list.scrollHeight
    })
  }, [activeChatId, messages.length])

  const updateActiveChat = (updater) => {
    setChats((current) =>
      current.map((chat) => {
        if (chat.id !== activeChat?.id) return chat
        return { ...updater(chat), updatedAt: new Date().toISOString() }
      })
    )
  }

  const sendMessage = (text = input) => {
    const content = text.trim()
    const chatId = activeChat?.id
    if (!content || !chatId) return
    const pendingMessage = createPendingMessage()

    updateActiveChat((chat) => {
      const shouldRename = chat.title === "Nova triagem" && chat.messages.length === 1
      return {
        ...chat,
        title: shouldRename ? titleFromMessage(content) : chat.title,
        messages: [...chat.messages, { role: "user", text: content }, pendingMessage],
      }
    })
    setInput("")

    const timeoutId = setTimeout(() => {
      setChats((current) =>
        current.map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                updatedAt: new Date().toISOString(),
                messages: chat.messages.map((message) =>
                  message.id === pendingMessage.id
                    ? { role: "assistant", text: makeReply(content, data) }
                    : message
                ),
              }
            : chat
        )
      )
      replyTimeoutsRef.current = replyTimeoutsRef.current.filter((id) => id !== timeoutId)
    }, replyDelayMs)

    replyTimeoutsRef.current.push(timeoutId)
  }

  const createNewChat = () => {
    const chat = createChat()
    setChats((current) => [chat, ...current])
    setActiveChatId(chat.id)
    setInput("")
    setMobileHistoryOpen(false)
  }

  const deleteChat = (chatId) => {
    setChats((current) => {
      const remaining = current.filter((chat) => chat.id !== chatId)
      if (!remaining.length) {
        const chat = createChat()
        setActiveChatId(chat.id)
        return [chat]
      }
      if (activeChatId === chatId) setActiveChatId(remaining[0].id)
      return remaining
    })
    if (editingChatId === chatId) {
      setEditingChatId("")
      setEditingTitle("")
    }
  }

  const startRename = (chat) => {
    setEditingChatId(chat.id)
    setEditingTitle(chat.title)
  }

  const saveRename = () => {
    const title = editingTitle.trim()
    if (!title) return

    setChats((current) =>
      current.map((chat) =>
        chat.id === editingChatId
          ? { ...chat, title, updatedAt: new Date().toISOString() }
          : chat
      )
    )
    setEditingChatId("")
    setEditingTitle("")
  }

  const toggleVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      updateActiveChat((chat) => ({
        ...chat,
        messages: [
          ...chat.messages,
          { role: "assistant", text: "Reconhecimento de voz não disponível neste navegador. Você pode digitar os sintomas." },
        ],
      }))
      return
    }

    if (!recognitionRef.current) {
      const recognition = new SpeechRecognition()
      recognition.lang = "pt-BR"
      recognition.continuous = false
      recognition.interimResults = false
      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map((result) => result[0]?.transcript || "")
          .join(" ")
          .trim()
        if (transcript) setInput((current) => `${current} ${transcript}`.trim())
      }
      recognition.onend = () => setListening(false)
      recognitionRef.current = recognition
    }

    if (listening) {
      recognitionRef.current.stop()
      setListening(false)
    } else {
      recognitionRef.current.start()
      setListening(true)
    }
  }

  return (
    <main className="chat-page">
      <section className="chat-shell" aria-label="Chat Swine DataMed">
        <aside className="chat-sidebar">
          <div className="chat-brand">
            <img src="/logos/compass_logo.png" alt="" />
            <div>
              <strong>Swine DataMed</strong>
              <span>Triagem assistida</span>
            </div>
          </div>

          <button type="button" className="chat-new" onClick={createNewChat}>
            <Plus size={18} />
            Nova conversa
          </button>

          <div className="chat-history">
            <span>Conversas</span>
            {chats.map((chat) => (
              <article className={chat.id === activeChat?.id ? "is-active" : ""} key={chat.id}>
                {editingChatId === chat.id ? (
                  <input
                    value={editingTitle}
                    onChange={(event) => setEditingTitle(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") saveRename()
                      if (event.key === "Escape") setEditingChatId("")
                    }}
                    autoFocus
                  />
                ) : (
                  <button type="button" onClick={() => setActiveChatId(chat.id)}>
                    {chat.title}
                  </button>
                )}

                <div>
                  {editingChatId === chat.id ? (
                    <>
                      <button type="button" onClick={saveRename} aria-label="Salvar nome">
                        <Check size={15} />
                      </button>
                      <button type="button" onClick={() => setEditingChatId("")} aria-label="Cancelar edição">
                        <X size={15} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button type="button" onClick={() => startRename(chat)} aria-label="Renomear conversa">
                        <Pencil size={15} />
                      </button>
                      <button type="button" onClick={() => deleteChat(chat.id)} aria-label="Excluir conversa">
                        <Trash2 size={15} />
                      </button>
                    </>
                  )}
                </div>
              </article>
            ))}
          </div>

          <div className="chat-note">
            <ShieldCheck size={20} />
            <p>As respostas organizam hipóteses e próximos passos. A decisão clínica deve ser validada por médico-veterinário.</p>
          </div>
        </aside>

        <section className="chat-main">
          <header className="chat-header">
            <div>
              <span>Swine Compass AI</span>
              <h1>{activeChat?.title || "Chat de apoio diagnóstico"}</h1>
            </div>
            <button
              type="button"
              className="chat-history-toggle"
              onClick={() => setMobileHistoryOpen((open) => !open)}
              aria-label="Abrir conversas antigas"
              aria-expanded={mobileHistoryOpen}
            >
              <Clock3 size={20} />
            </button>
            <Sparkles size={24} />
          </header>

          <div className={`chat-mobile-history ${mobileHistoryOpen ? "is-open" : ""}`}>
            <div className="chat-mobile-history-bar">
              <strong>Conversas antigas</strong>
              <button type="button" onClick={createNewChat}>
                <Plus size={17} />
                Nova
              </button>
            </div>

            <div className="chat-mobile-history-list">
              {chats.map((chat) => (
                <button
                  type="button"
                  className={chat.id === activeChat?.id ? "is-active" : ""}
                  key={chat.id}
                  onClick={() => {
                    setActiveChatId(chat.id)
                    setMobileHistoryOpen(false)
                  }}
                >
                  {chat.title}
                </button>
              ))}
            </div>
          </div>

          <div className="chat-messages" ref={messagesRef}>
            {messages.map((message, index) => (
              <article
                className={`chat-message chat-message--${message.role} ${message.pending ? "chat-message--pending" : ""}`}
                key={message.id || `${message.role}-${index}`}
              >
                <span className="chat-avatar">
                  {message.role === "assistant" ? <Bot size={20} /> : <UserRound size={20} />}
                </span>
                <p>{message.text}</p>
              </article>
            ))}
          </div>

          <form
            className="chat-input"
            onSubmit={(event) => {
              event.preventDefault()
              sendMessage()
            }}
          >
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  sendMessage()
                }
              }}
              placeholder="Digite sintomas, fase, idade, temperatura, quantidade de animais afetados..."
              rows={3}
            />
            <div>
              <button type="button" className={listening ? "is-listening" : ""} onClick={toggleVoice} aria-label="Usar voz">
                <Mic size={20} />
              </button>
              <button type="submit" aria-label="Enviar mensagem">
                <Send size={20} />
              </button>
            </div>
          </form>
        </section>
      </section>
    </main>
  )
}

export default Chat
