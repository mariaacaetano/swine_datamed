import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Mail, Lock } from "lucide-react"
import { loginUser } from "../../services/auth"
import "./Login.css"

function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [message, setMessage] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible")
          }
        })
      },
      { threshold: 0.15 }
    )
    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el))

    let animationFrame = 0
    const current = { shift: 0, card: 0 }
    const target = { ...current }

    const measureScroll = () => {
      const page = document.querySelector(".login-page")
      const viewport = window.innerHeight || 1
      const rect = page?.getBoundingClientRect()

      if (rect) {
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.shift = progress * 42
        target.card = progress * -10
      }
    }

    const render = () => {
      const page = document.querySelector(".login-page")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (page) {
        page.style.setProperty("--auth-bg-shift", `${current.shift.toFixed(2)}px`)
        page.style.setProperty("--auth-card-shift", `${current.card.toFixed(2)}px`)
      }

      animationFrame = requestAnimationFrame(render)
    }

    measureScroll()
    render()
    window.addEventListener("scroll", measureScroll, { passive: true })
    window.addEventListener("resize", measureScroll)

    return () => {
      observer.disconnect()
      cancelAnimationFrame(animationFrame)
      window.removeEventListener("scroll", measureScroll)
      window.removeEventListener("resize", measureScroll)
    }
  }, [])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage("")
    setIsSubmitting(true)

    try {
      await loginUser({ email, password })
      navigate("/perfil")
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-page__fade" aria-hidden="true" />
      <div className="login-container">

        <div className="login-brand reveal">
          <img src="/logos/pig_logo.png" alt="Swine DataMed" className="login-logo" />
          <span className="login-kicker">Swine DataMed</span>
          <h1>Acesse sua conta</h1>
          <p>Entre para continuar usando as ferramentas de apoio à sanidade suína.</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <h2 className="login-title reveal">Login</h2>

          <label className="login-field reveal">
            <Mail size={16} className="login-field-icon" />
            <input
              type="email"
              placeholder="Digite seu e-mail"
              className="login-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="login-field reveal">
            <Lock size={16} className="login-field-icon" />
            <input
              type="password"
              placeholder="Digite sua senha"
              className="login-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          <Link to="/recuperar-senha" className="login-forgot reveal">Esqueceu a senha?</Link>

          {message && <p className="login-message reveal">{message}</p>}

          <button className="login-btn reveal" disabled={isSubmitting}>
            {isSubmitting ? "Entrando..." : "Entrar"}
          </button>

          <p className="login-register reveal">
            Ainda não tem uma conta?{" "}
            <Link to="/cadastro">Cadastre-se.</Link>
          </p>
        </form>

      </div>
    </main>
  )
}

export default Login
