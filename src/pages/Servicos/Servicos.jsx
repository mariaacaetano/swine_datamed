import { useEffect } from "react"
import { Link } from "react-router-dom"
import {
  Activity,
  Calculator,
  ChevronRight,
  PackageSearch,
} from "lucide-react"
import "./Servicos.css"

const serviceCards = [
  {
    icon: Activity,
    title: "Swine Compass",
    text: "Triagem visual para organizar sinais clínicos, comparar hipóteses e reunir próximos passos de cuidado para avaliação técnica.",
    action: "Abrir Compass",
    to: "/compass",
  },
  {
    icon: PackageSearch,
    title: "Swine Package",
    text: "Consulta de medicamentos por nome comercial ou princípio ativo, com foco em leitura rápida e apoio ao uso responsável.",
    action: "Abrir Package",
    to: "/bulario",
  },
  {
    icon: Calculator,
    title: "Swine Calc",
    text: "Área para cálculos de apoio, dosagens, conferências e organização de parâmetros usados na rotina de manejo.",
    action: "Abrir Calc",
    to: "/calc",
  },
]

function Servicos() {
  useEffect(() => {
    let animationFrame = 0
    const current = { feature: 0, mascot: 0, cards: 0 }
    const target = { ...current }

    const measureScroll = () => {
      const page = document.querySelector(".services-page")
      const feature = document.querySelector(".services-feature")
      const viewport = window.innerHeight || 1

      if (feature) {
        const rect = feature.getBoundingClientRect()
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.feature = progress * -18
        target.mascot = progress * 14
        target.cards = progress * -20
      }

      page?.style.setProperty("--services-ready", "1")
    }

    const renderScrollEffects = () => {
      const page = document.querySelector(".services-page")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (page) {
        page.style.setProperty("--feature-shift", `${current.feature.toFixed(2)}px`)
        page.style.setProperty("--mascot-scroll-shift", `${current.mascot.toFixed(2)}px`)
        page.style.setProperty("--cards-shift", `${current.cards.toFixed(2)}px`)
      }

      animationFrame = requestAnimationFrame(renderScrollEffects)
    }

    measureScroll()
    renderScrollEffects()
    window.addEventListener("scroll", measureScroll, { passive: true })
    window.addEventListener("resize", measureScroll)

    return () => {
      cancelAnimationFrame(animationFrame)
      window.removeEventListener("scroll", measureScroll)
      window.removeEventListener("resize", measureScroll)
    }
  }, [])

  return (
    <main className="services-page">
      <section className="services-dashboard" aria-label="Serviços Swine DataMed">
        <div className="services-feature">
          <div>
            <span>Serviços</span>
            <h1>Ferramentas para decisões mais claras na suinocultura</h1>
            <p>
              O Swine DataMed organiza consulta de medicamentos, apoio diagnóstico e
              fluxos de cuidado em uma interface feita para leitura rápida.
            </p>
          </div>
        </div>

        <div className="services-cards">
          {serviceCards.map(({ icon: Icon, title, text, action, to }) => (
            <Link to={to} key={title}>
              <Icon size={30} />
              <strong>{title}</strong>
              <p>{text}</p>
              <span>
                {action}
                <ChevronRight size={18} />
              </span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  )
}

export default Servicos
