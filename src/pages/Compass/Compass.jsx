import { useEffect } from "react"
import { Link } from "react-router-dom"
import { Activity, ChevronRight, ClipboardList, HeartPulse, ShieldCheck } from "lucide-react"
import "./Compass.css"

function Compass() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) entry.target.classList.add("visible")
        })
      },
      { threshold: 0.15 }
    )

    document.querySelectorAll(".reveal").forEach((el) => observer.observe(el))

    let animationFrame = 0
    const current = { shift: 0, copyShift: 0, fade: 0 }
    const target = { ...current }

    const measureScroll = () => {
      const card = document.querySelector(".compass-card")
      const viewport = window.innerHeight || 1

      if (card) {
        const rect = card.getBoundingClientRect()
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.shift = progress * 48
        target.copyShift = progress * -14
        target.fade = Math.max(0, progress) * 0.28
      }

    }

    const renderScrollEffects = () => {
      const card = document.querySelector(".compass-card")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (card) {
        card.style.setProperty("--compass-shift", `${current.shift.toFixed(2)}px`)
        card.style.setProperty("--compass-copy-shift", `${current.copyShift.toFixed(2)}px`)
        card.style.setProperty("--compass-fade", current.fade.toFixed(3))
      }

      animationFrame = requestAnimationFrame(renderScrollEffects)
    }

    measureScroll()
    renderScrollEffects()
    window.addEventListener("scroll", measureScroll, { passive: true })
    window.addEventListener("resize", measureScroll)

    return () => {
      observer.disconnect()
      cancelAnimationFrame(animationFrame)
      window.removeEventListener("scroll", measureScroll)
      window.removeEventListener("resize", measureScroll)
    }
  }, [])

  return (
    <main className="compass">
      <section className="compass-stage reveal">
        <div className="compass-card">
          <div className="compass-copy">
            <span>Swine Compass</span>
            <h1>Mapa de apoio ao diagnóstico</h1>
            <p>
              Uma jornada guiada para observar sintomas, organizar sinais clínicos e
              encontrar possíveis caminhos de cuidado para suínos.
            </p>
            <Link to="/chat" className="compass-main-action">
              Começar triagem
              <ChevronRight size={22} />
            </Link>
          </div>

          <div className="compass-card__fade" aria-hidden="true" />
        </div>
      </section>

      <section className="compass-info reveal" id="sobre">
        <article>
          <Activity size={32} />
          <h2>Triagem</h2>
          <p>Organize sinais como apetite, respiração, pele, comportamento e evolução.</p>
        </article>
        <article id="triagem">
          <ClipboardList size={32} />
          <h2>Hipóteses</h2>
          <p>Compare padrões de sintomas e prepare informações para avaliação técnica.</p>
        </article>
        <article id="cuidados">
          <HeartPulse size={32} />
          <h2>Conduta</h2>
          <p>Acesse recomendações, próximos passos e consulta ao Swine Package quando necessário.</p>
        </article>
        <article>
          <ShieldCheck size={32} />
          <h2>Segurança</h2>
          <p>Use o sistema como apoio e preserve a decisão clínica do profissional.</p>
        </article>
      </section>
    </main>
  )
}

export default Compass
