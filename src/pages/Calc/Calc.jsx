import { useEffect } from "react"
import { Calculator, ClipboardCheck, Ruler, ShieldCheck } from "lucide-react"
import "./Calc.css"

function Calc() {
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
      const card = document.querySelector(".calc-card")
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
      const card = document.querySelector(".calc-card")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (card) {
        card.style.setProperty("--calc-shift", `${current.shift.toFixed(2)}px`)
        card.style.setProperty("--calc-copy-shift", `${current.copyShift.toFixed(2)}px`)
        card.style.setProperty("--calc-fade", current.fade.toFixed(3))
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
    <main className="calc">
      <section className="calc-stage reveal">
        <div className="calc-card">
          <div className="calc-copy">
            <span>Swine Calc</span>
            <h1>Calculadora de apoio</h1>
            <p>
              Estruture cálculos de dose, peso, volume e conferência de manejo em um
              espaço pensado para futuras rotinas da plataforma.
            </p>
            <button type="button" className="calc-main-action">
              Preparar cálculo
              <Calculator size={22} />
            </button>
          </div>

          <div className="calc-card__fade" aria-hidden="true" />
        </div>
      </section>

      <section className="calc-info reveal">
        <article>
          <Calculator size={32} />
          <h2>Dose</h2>
          <p>Base para estimar e conferir cálculos ligados à rotina de medicamentos.</p>
        </article>
        <article>
          <Ruler size={32} />
          <h2>Parâmetros</h2>
          <p>Organize peso, volume, concentração e unidades antes da tomada de decisão.</p>
        </article>
        <article>
          <ClipboardCheck size={32} />
          <h2>Conferência</h2>
          <p>Padronize etapas de checagem para reduzir erros de leitura e registro.</p>
        </article>
        <article>
          <ShieldCheck size={32} />
          <h2>Segurança</h2>
          <p>Use os cálculos como apoio e preserve a orientação profissional.</p>
        </article>
      </section>
    </main>
  )
}

export default Calc
