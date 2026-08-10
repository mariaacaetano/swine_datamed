import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Beaker,
  ChevronRight,
  Download,
  PackageSearch,
  Search,
  ShieldCheck,
  Stethoscope,
} from "lucide-react"
import { buildData, normalize } from "../../data/swineKnowledge"
import "./Bulario.css"

const emptyValue = "Informação não preenchida na base atual."

function slugify(value) {
  return normalize(value)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
}

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

function getField(item, field) {
  const value = item?.[field]
  if (!value || ["—", "-", "completar"].includes(normalize(value).trim())) return emptyValue
  return value
}

function scoreMedicine(farmaco, query, diseaseHints) {
  const normalizedQuery = normalize(query)
  const searchable = normalize(
    [
      farmaco["Nome comercial"],
      farmaco["Princípio ativo"],
      farmaco.Classe,
      farmaco["Indicações principais"],
      farmaco["Mecanismo de ação"],
    ].join(" ")
  )
  let score = 0

  if (!normalizedQuery) return 1
  if (normalize(farmaco["Nome comercial"]).includes(normalizedQuery)) score += 8
  if (normalize(farmaco["Princípio ativo"]).includes(normalizedQuery)) score += 7
  if (normalize(farmaco.Classe).includes(normalizedQuery)) score += 4
  if (normalize(farmaco["Indicações principais"]).includes(normalizedQuery)) score += 5
  if (searchable.includes(normalizedQuery)) score += 2

  diseaseHints.forEach((disease) => {
    if (normalize(farmaco["Indicações principais"]).includes(normalize(disease))) score += 5
  })

  return score
}

function findDiseaseHints(query, sintomas, doencas) {
  const normalizedQuery = normalize(query)
  if (!normalizedQuery) return []

  const hints = new Set()

  sintomas.forEach((row) => {
    const symptom = normalize(row.SINTOMA)
    if (symptom && (symptom.includes(normalizedQuery) || normalizedQuery.includes(symptom))) {
      splitList(row["DOENÇAS ASSOCIADAS"]).forEach((disease) => hints.add(disease))
    }
  })

  doencas.forEach((row) => {
    const disease = row["DOENÇA"]
    const diseaseText = normalize([disease, row.SINTOMAS, row.TIPO, row["FASE COMUM"]].join(" "))
    if (diseaseText.includes(normalizedQuery)) hints.add(disease)
  })

  return [...hints]
}

function pdfText(value) {
  return String(value || "")
    .replace(/[–—→]/g, "-")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
}

function escapePdfText(value) {
  return pdfText(value).replace(/[\s\S]/g, (char) => {
    if (char === "\\") return "\\\\"
    if (char === "(") return "\\("
    if (char === ")") return "\\)"
    if (char === "\n") return "\\n"

    const code = char.charCodeAt(0)
    if (code >= 32 && code <= 126) return char
    if (code <= 255) return `\\${code.toString(8).padStart(3, "0")}`
    return ""
  })
}

function wrapPdfText(text, maxLength = 82) {
  const words = pdfText(text).split(/\s+/).filter(Boolean)
  const lines = []
  let line = ""

  words.forEach((word) => {
    const nextLine = line ? `${line} ${word}` : word
    if (nextLine.length > maxLength && line) {
      lines.push(line)
      line = word
    } else {
      line = nextLine
    }
  })

  if (line) lines.push(line)
  return lines.length ? lines : [pdfText(emptyValue)]
}

function bytesToHex(bytes) {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("")
}

function loadPigLogoForPdf() {
  return new Promise((resolve) => {
    const image = new Image()

    image.onload = () => {
      const size = 96
      const canvas = document.createElement("canvas")
      const context = canvas.getContext("2d")
      const scale = Math.min(size / image.width, size / image.height)
      const width = image.width * scale
      const height = image.height * scale
      const x = (size - width) / 2
      const y = (size - height) / 2

      canvas.width = size
      canvas.height = size
      context.fillStyle = "#ffffff"
      context.fillRect(0, 0, size, size)
      context.drawImage(image, x, y, width, height)

      const base64 = canvas.toDataURL("image/jpeg", 0.88).split(",")[1]
      const binary = atob(base64)
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))

      resolve({ hex: bytesToHex(bytes), width: size, height: size })
    }

    image.onerror = () => resolve(null)
    image.src = "/logos/pig_logo.png"
  })
}

function buildBulaPdf(farmaco, pigLogo) {
  const title = pdfText(farmaco["Nome comercial"] || "Medicamento")
  const generatedAt = new Date().toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  })
  const sections = [
    ["1. IDENTIFICAÇÃO DO PRODUTO", `Nome comercial: ${title}. Princípio ativo: ${getField(farmaco, "Princípio ativo")}. Classe: ${getField(farmaco, "Classe")}.`],
    ["2. COMPOSIÇÃO E AÇÃO", `Mecanismo de ação: ${getField(farmaco, "Mecanismo de ação")}`],
    ["3. INDICAÇÕES", getField(farmaco, "Indicações principais")],
    ["4. POSOLOGIA E MODO DE USO", `Posologia: ${getField(farmaco, "Posologia")}. Via de administração: ${getField(farmaco, "Via administração")}.`],
    ["5. PERÍODO DE CARÊNCIA", getField(farmaco, "Carência")],
    ["6. CONTRAINDICAÇÕES", getField(farmaco, "Contraindicações")],
    ["7. REAÇÕES ADVERSAS", getField(farmaco, "Reações adversas")],
    ["8. PRECAUÇÕES", getField(farmaco, "Precauções")],
  ]

  const content = [
    "0 g",
    "1 w",
    "36 808 m 559 808 l S",
    "36 690 m 559 690 l S",
    "296 690 m 296 88 l S",
  ]
  const columns = [
    { x: 44, y: 660, width: 236 },
    { x: 314, y: 512, width: 236 },
  ]
  let column = 0

  const addTextAt = (text, x, y, size = 9, font = "F1") => {
    content.push(`BT /${font} ${size} Tf ${x} ${y} Td (${escapePdfText(text)}) Tj ET`)
  }

  const addLine = (x1, y1, x2, y2) => {
    content.push(`${x1} ${y1} m ${x2} ${y2} l S`)
  }

  const addBox = (x, y, width, height) => {
    content.push(`${x} ${y} ${width} ${height} re S`)
  }

  const addFilledBox = (x, y, width, height, gray = 0.94) => {
    content.push(`${gray} g ${x} ${y} ${width} ${height} re f 0 g`)
  }

  const addCircle = (cx, cy, radius) => {
    const c = radius * 0.55228475
    content.push(
      `${cx + radius} ${cy} m ${cx + radius} ${cy + c} ${cx + c} ${cy + radius} ${cx} ${cy + radius} c ${cx - c} ${cy + radius} ${cx - radius} ${cy + c} ${cx - radius} ${cy} c ${cx - radius} ${cy - c} ${cx - c} ${cy - radius} ${cx} ${cy - radius} c ${cx + c} ${cy - radius} ${cx + radius} ${cy - c} ${cx + radius} ${cy} c f`
    )
  }

  const addPigLogoMark = (x, y) => {
    content.push("0.95 0.72 0.80 rg")
    addCircle(x + 12, y + 12, 11)
    addCircle(x + 4, y + 22, 4)
    addCircle(x + 20, y + 22, 4)
    addCircle(x + 12, y + 8, 4.8)
    content.push("0.10 0.22 0.12 rg")
    addCircle(x + 8, y + 13, 1.4)
    addCircle(x + 14, y + 13, 1.4)
    addCircle(x + 10.5, y + 8, 0.9)
    addCircle(x + 13.5, y + 8, 0.9)
    content.push("0 g")
  }

  const addBoxText = (text, x, startY, maxLines, maxLength, size = 7.3, leading = 9) => {
    wrapPdfText(text, maxLength)
      .slice(0, maxLines)
      .forEach((line, index) => addTextAt(line, x, startY - index * leading, size))
  }

  const nextColumn = () => {
    if (column + 1 >= columns.length) return false
    column += 1
    return true
  }

  const addColumnText = (text, size = 8.6, leading = 10.5, indent = 0, maxLength = 51) => {
    for (const line of wrapPdfText(text, maxLength)) {
      if (columns[column].y < 88 && !nextColumn()) break
      addTextAt(line, columns[column].x + indent, columns[column].y, size)
      columns[column].y -= leading
    }
  }

  const addSection = ([label, value]) => {
    if (columns[column].y < 118 && !nextColumn()) return
    columns[column].y -= 8
    addTextAt(label, columns[column].x, columns[column].y, 9.6, "F2")
    columns[column].y -= 12
    addColumnText(value, 8.4, 10.2, 0, 52)
  }

  addTextAt("Swine Package", 44, 790, 9, "F2")
  addTextAt("BULA VETERINÁRIA DIGITAL", 44, 770, 12, "F2")
  addTextAt(title.toUpperCase(), 44, 742, 28, "F2")
  addTextAt(`Gerada pelo Swine DataMed em ${generatedAt}`, 44, 718, 8.5)
  addTextAt("Documento automático para consulta, estudo e testes da aplicação.", 44, 704, 8.5)

  addFilledBox(314, 558, 236, 100, 0.96)
  addBox(314, 558, 236, 100)
  addTextAt("USO COM ORIENTAÇÃO PROFISSIONAL", 326, 636, 8.8, "F2")
  addBoxText(
    "Consulte um médico-veterinário. Esta bula é gerada automaticamente pelo Swine DataMed para apoio, estudo e testes; não substitui prescrição, bula oficial ou avaliação clínica.",
    326,
    618,
    6,
    48,
    7.2,
    9
  )

  sections.forEach(addSection)

  addLine(36, 70, 559, 70)
  if (pigLogo) {
    content.push("q 28 0 0 28 42 30 cm /PigLogo Do Q")
  } else {
    addPigLogoMark(44, 34)
  }
  addTextAt("Swine DataMed", 76, 50, 9, "F2")
  addTextAt("Bula digital gerada automaticamente. Validar dados antes de qualquer uso em campo.", 76, 38, 7.2)

  const stream = content.join("\n")
  const pageResources = pigLogo
    ? "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> /XObject << /PigLogo 6 0 R >> >> /Contents 7 0 R"
    : "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R"
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] ${pageResources} >>`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
  ]

  if (pigLogo) {
    objects.push(
      `<< /Type /XObject /Subtype /Image /Width ${pigLogo.width} /Height ${pigLogo.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter [/ASCIIHexDecode /DCTDecode] /Length ${pigLogo.hex.length + 1} >>\nstream\n${pigLogo.hex}>\nendstream`
    )
  }

  objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`)

  let pdf = "%PDF-1.4\n"
  const offsets = [0]

  objects.forEach((object, index) => {
    offsets.push(pdf.length)
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`
  })

  const xrefOffset = pdf.length
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
  offsets.slice(1).forEach((offset) => {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`
  })
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`

  return pdf
}

function Bulario() {
  const data = useMemo(() => buildData(), [])
  const navigate = useNavigate()
  const { slug } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [busca, setBusca] = useState(searchParams.get("q") || "")
  const activeMedicine = useMemo(
    () => data.farmacos.find((farmaco) => slugify(farmaco["Nome comercial"]) === slug),
    [data.farmacos, slug]
  )

  const diseaseHints = useMemo(
    () => findDiseaseHints(busca, data.sintomas, data.doencas),
    [busca, data.sintomas, data.doencas]
  )

  const results = useMemo(() => {
    const scored = data.farmacos
      .map((farmaco) => ({ farmaco, score: scoreMedicine(farmaco, busca, diseaseHints) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || a.farmaco["Nome comercial"].localeCompare(b.farmaco["Nome comercial"]))

    return scored.map((item) => item.farmaco)
  }, [busca, data.farmacos, diseaseHints])

  useEffect(() => {
    const root = document.querySelector(".bulario")
    const revealEls = root ? [...root.querySelectorAll(".reveal")] : []
    let observer
    let animationFrame = 0
    let revealFrame = 0
    const current = { shift: 0, copyShift: 0, fade: 0 }
    const target = { ...current }

    const showVisibleReveals = () => {
      const viewport = window.innerHeight || 1
      revealEls.forEach((el) => {
        const rect = el.getBoundingClientRect()
        if (rect.top < viewport * 0.96 && rect.bottom > 0) el.classList.add("visible")
      })
    }

    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) entry.target.classList.add("visible")
          })
        },
        { threshold: 0.08, rootMargin: "0px 0px -8% 0px" }
      )

      revealEls.forEach((el) => observer.observe(el))
    } else {
      revealEls.forEach((el) => el.classList.add("visible"))
    }

    const measureScroll = () => {
      const hero = document.querySelector(".package-hero")
      const viewport = window.innerHeight || 1

      if (hero) {
        const rect = hero.getBoundingClientRect()
        const progress = Math.min(1, Math.max(-1, (viewport / 2 - rect.top) / viewport))
        target.shift = progress * 48
        target.copyShift = progress * -14
        target.fade = Math.max(0, progress) * 0.28
      }
    }

    const renderScrollEffects = () => {
      const hero = document.querySelector(".package-hero")
      const ease = 0.085

      Object.keys(current).forEach((key) => {
        current[key] += (target[key] - current[key]) * ease
      })

      if (hero) {
        hero.style.setProperty("--package-shift", `${current.shift.toFixed(2)}px`)
        hero.style.setProperty("--package-copy-shift", `${current.copyShift.toFixed(2)}px`)
        hero.style.setProperty("--package-fade", current.fade.toFixed(3))
      }

      animationFrame = requestAnimationFrame(renderScrollEffects)
    }

    measureScroll()
    showVisibleReveals()
    revealFrame = requestAnimationFrame(showVisibleReveals)
    renderScrollEffects()
    window.addEventListener("scroll", measureScroll, { passive: true })
    window.addEventListener("resize", measureScroll)

    return () => {
      observer?.disconnect()
      cancelAnimationFrame(animationFrame)
      cancelAnimationFrame(revealFrame)
      window.removeEventListener("scroll", measureScroll)
      window.removeEventListener("resize", measureScroll)
    }
  }, [slug])

  const submitSearch = (event) => {
    event.preventDefault()
    if (busca.trim()) {
      setSearchParams({ q: busca.trim() })
      navigate(`/bulario?q=${encodeURIComponent(busca.trim())}`)
    } else {
      setSearchParams({})
      navigate("/bulario")
    }
  }

  const downloadBula = async () => {
    if (!activeMedicine) return

    const pigLogo = await loadPigLogoForPdf()
    const pdf = buildBulaPdf(activeMedicine, pigLogo)
    const blob = new Blob([pdf], { type: "application/pdf" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")

    link.href = url
    link.download = `${slugify(activeMedicine["Nome comercial"])}-bula.pdf`
    link.click()
    URL.revokeObjectURL(url)
  }

  if (slug) {
    if (!activeMedicine) {
      return (
        <main className="bulario">
          <section className="package-detail package-detail--empty">
            <Link to="/bulario" className="package-back">
              <ArrowLeft size={18} />
              Voltar ao Swine Package
            </Link>
            <h1>Medicamento não encontrado</h1>
            <p>Esse registro não está disponível entre os fármacos preenchidos da base atual.</p>
          </section>
        </main>
      )
    }

    return (
      <main className="bulario">
        <section className="package-detail reveal">
          <aside className="package-detail__nav">
            <Link to="/bulario" className="package-back">
              <ArrowLeft size={18} />
              Busca
            </Link>
          </aside>

          <article className="package-detail__content">
            <div className="package-detail__headline" id="sobre">
              <span>Swine Package</span>
              <h1>
                {activeMedicine["Nome comercial"]}
                <button
                  type="button"
                  className="package-download"
                  onClick={downloadBula}
                  aria-label={`Baixar bula de ${activeMedicine["Nome comercial"]}`}
                >
                  <Download size={28} />
                </button>
              </h1>
              <p>{getField(activeMedicine, "Princípio ativo")}</p>
            </div>

            <div className="package-detail__grid">
              <section>
                <Beaker size={24} />
                <h2>Receita e composição</h2>
                <dl>
                  <dt>Classe</dt>
                  <dd>{getField(activeMedicine, "Classe")}</dd>
                  <dt>Mecanismo de ação</dt>
                  <dd>{getField(activeMedicine, "Mecanismo de ação")}</dd>
                </dl>
              </section>

              <section id="indicacoes">
                <Stethoscope size={24} />
                <h2>Indicações</h2>
                <p>{getField(activeMedicine, "Indicações principais")}</p>
              </section>

              <section id="uso">
                <BadgeCheck size={24} />
                <h2>Posologia e via</h2>
                <dl>
                  <dt>Posologia</dt>
                  <dd>{getField(activeMedicine, "Posologia")}</dd>
                  <dt>Via de administração</dt>
                  <dd>{getField(activeMedicine, "Via administração")}</dd>
                  <dt>Carência</dt>
                  <dd>{getField(activeMedicine, "Carência")}</dd>
                </dl>
              </section>

              <section id="seguranca">
                <AlertTriangle size={24} />
                <h2>Segurança</h2>
                <dl>
                  <dt>Contraindicações</dt>
                  <dd>{getField(activeMedicine, "Contraindicações")}</dd>
                  <dt>Reações adversas</dt>
                  <dd>{getField(activeMedicine, "Reações adversas")}</dd>
                  <dt>Precauções</dt>
                  <dd>{getField(activeMedicine, "Precauções")}</dd>
                </dl>
              </section>
            </div>
          </article>
        </section>
      </main>
    )
  }

  return (
    <main className="bulario">
      <section className="package-hero reveal">
        <div className="package-copy">
          <span>Swine Package</span>
          <h1>Bulário inteligente</h1>
          <p>
            Consulte por fármaco, nome comercial, princípio ativo, sintoma ou doença.
            A busca cruza os dados preenchidos da base para encontrar o registro mais útil.
          </p>
          <form className="package-search" onSubmit={submitSearch}>
            <input
              type="text"
              placeholder="Busque por medicamento, sintoma ou doença..."
              value={busca}
              onChange={(event) => setBusca(event.target.value)}
            />
            <button aria-label="Buscar">
              <Search size={22} />
            </button>
          </form>
        </div>

        <div className="package-hero__fade" aria-hidden="true" />
      </section>

      <section className="package-results reveal">
        <div className="package-results__head">
          <div>
            <span>Consulta</span>
            <h2>{busca.trim() ? `Resultados para "${busca.trim()}"` : "Medicamentos disponíveis"}</h2>
          </div>
          <strong>{results.length} registros</strong>
        </div>

        {diseaseHints.length > 0 && (
          <div className="package-hints">
            <ShieldCheck size={20} />
            <p>
              A busca reconheceu relação com: <strong>{diseaseHints.slice(0, 4).join(", ")}</strong>.
            </p>
          </div>
        )}

        <div className="package-list">
          {results.map((farmaco, idx) => (
            <Link to={`/bulario/${slugify(farmaco["Nome comercial"])}`} className="package-card" key={`${farmaco["Nome comercial"]}-${idx}`}>

              <PackageSearch size={26} />
              <div>
                <h3>{farmaco["Nome comercial"]}</h3>
                <p>{farmaco["Princípio ativo"]}</p>
                <small>{farmaco["Indicações principais"]}</small>
              </div>
              <span>
                Acessar
                <ChevronRight size={18} />
              </span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  )
}

export default Bulario
