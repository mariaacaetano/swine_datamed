import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, CalendarDays, ClipboardList, ImagePlus, Pencil, Plus, Save, Syringe, UserRound, X } from "lucide-react"
import { buildData, normalize } from "../../data/swineKnowledge"
import { getAuth } from "../../services/auth"
import { createMedication, createPig, listMedications, listPigs, updatePig } from "../../services/suinos"
import "./Suinos.css"

const today = new Date().toISOString().slice(0, 10)
const emptyMedicationValues = new Set(["", "—", "-", "completar"])
const lifeStageLabels = {
  leitao: "Leitão",
  creche: "Creche",
  crescimento: "Crescimento",
  terminacao: "Terminação",
  matriz: "Matriz",
  reprodutor: "Reprodutor",
}
const sizeLabels = {
  pequeno: "Pequeno",
  medio: "Médio",
  grande: "Grande",
}

const emptyPigForm = {
  name: "",
  tag: "",
  breed: "",
  sex: "",
  life_stage: "",
  size_category: "",
  pen: "",
  origin: "",
  birth_date: "",
  weight_kg: "",
  status: "ativo",
  notes: "",
}

const emptyMedicationForm = {
  pig: "",
  medicine_name: "",
  active_principle: "",
  dose: "",
  route: "outra",
  applied_at: today,
  withdrawal_until: "",
  responsible: "",
  notes: "",
}

function isFilledMedicationValue(value) {
  return !emptyMedicationValues.has(normalize(value).trim())
}

function routeFromMedication(value) {
  const route = normalize(value)

  if (route.includes("oral")) return "oral"
  if (route.includes("intramuscular") || /\bim\b/.test(route)) return "intramuscular"
  if (route.includes("subcut")) return "subcutanea"
  if (route.includes("topic")) return "topica"
  return "outra"
}

function addDays(dateValue, days) {
  if (!dateValue || !Number.isFinite(days)) return ""

  const date = new Date(`${dateValue}T00:00:00`)
  date.setDate(date.getDate() + Math.max(0, Math.ceil(days)))
  return date.toISOString().slice(0, 10)
}

function withdrawalDateFromMedication(carencia, appliedAt) {
  const text = normalize(carencia)
  if (!isFilledMedicationValue(text)) return ""

  const dayMatch = text.match(/(\d+(?:[.,]\d+)?)\s*d/)
  if (dayMatch) return addDays(appliedAt, Number(dayMatch[1].replace(",", ".")))

  const hourMatch = text.match(/(\d+(?:[.,]\d+)?)\s*h/)
  if (hourMatch) return addDays(appliedAt, Number(hourMatch[1].replace(",", ".")) / 24)

  return ""
}

function pigFormFromRecord(pig) {
  if (!pig) return emptyPigForm

  return {
    name: pig.name || "",
    tag: pig.tag || "",
    breed: pig.breed || "",
    sex: pig.sex || "",
    life_stage: pig.life_stage || "",
    size_category: pig.size_category || "",
    pen: pig.pen || "",
    origin: pig.origin || "",
    birth_date: pig.birth_date || "",
    weight_kg: pig.weight_kg || "",
    status: pig.status || "ativo",
    notes: pig.notes || "",
  }
}

function buildPigPayload(form, photo) {
  const payload = new FormData()

  Object.entries(form).forEach(([key, value]) => {
    if (value !== "") payload.append(key, value)
  })
  if (photo) payload.append("photo", photo)

  return payload
}

function displayOption(value, labels, fallback = "Não informado") {
  return value ? labels[value] || value : fallback
}

function Suinos() {
  const swineData = useMemo(() => buildData(), [])
  const availableMedications = swineData.farmacos
  const { pigId } = useParams()
  const [pigs, setPigs] = useState([])
  const [medications, setMedications] = useState([])
  const [pigForm, setPigForm] = useState(emptyPigForm)
  const [medicationForm, setMedicationForm] = useState(emptyMedicationForm)
  const [selectedPigId, setSelectedPigId] = useState("")
  const [message, setMessage] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isSavingPig, setIsSavingPig] = useState(false)
  const [isUpdatingPig, setIsUpdatingPig] = useState(false)
  const [isSavingMedication, setIsSavingMedication] = useState(false)
  const [pigPhoto, setPigPhoto] = useState(null)
  const [pigPhotoPreview, setPigPhotoPreview] = useState("")
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editPigDraft, setEditPigDraft] = useState({
    pigId: "",
    form: emptyPigForm,
    photo: null,
    preview: "",
  })
  const navigate = useNavigate()

  useEffect(() => {
    let isActive = true

    if (!getAuth()?.token) {
      navigate("/login")
      return undefined
    }

    async function loadData() {
      setIsLoading(true)
      setMessage("")

      try {
        const [pigData, medicationData] = await Promise.all([listPigs(), listMedications()])
        if (!isActive) return
        setPigs(pigData)
        setMedications(medicationData)
        const initialPigId = pigId || pigData[0]?.id
        if (initialPigId) {
          setSelectedPigId(String(initialPigId))
          setMedicationForm((current) => ({ ...current, pig: String(initialPigId) }))
        }
      } catch (error) {
        if (isActive) setMessage(error.message)
      } finally {
        if (isActive) setIsLoading(false)
      }
    }

    loadData()

    return () => {
      isActive = false
    }
  }, [navigate, pigId])

  const selectedPig = useMemo(
    () => pigs.find((pig) => String(pig.id) === String(selectedPigId)),
    [pigs, selectedPigId]
  )

  const activeEditPigForm =
    editPigDraft.pigId === String(selectedPig?.id) ? editPigDraft.form : pigFormFromRecord(selectedPig)
  const activeEditPigPhotoPreview = editPigDraft.pigId === String(selectedPig?.id) ? editPigDraft.preview : ""
  const activeEditPigPhoto = editPigDraft.pigId === String(selectedPig?.id) ? editPigDraft.photo : null

  const selectedPigMedications = useMemo(
    () =>
      medications
        .filter((record) => String(record.pig) === String(selectedPigId))
        .sort((a, b) => String(b.applied_at || "").localeCompare(String(a.applied_at || ""))),
    [medications, selectedPigId]
  )

  const selectedMedication = useMemo(
    () => availableMedications.find((medication) => medication["Nome comercial"] === medicationForm.medicine_name),
    [availableMedications, medicationForm.medicine_name]
  )

  const dashboard = useMemo(() => {
    const treatmentCount = pigs.filter((pig) => pig.status === "tratamento").length
    const currentMonth = new Date().toISOString().slice(0, 7)
    const monthMedicationCount = medications.filter((record) => record.applied_at?.startsWith(currentMonth)).length

    return {
      totalPigs: pigs.length,
      treatmentCount,
      medicationCount: medications.length,
      monthMedicationCount,
    }
  }, [pigs, medications])

  const handlePigChange = (event) => {
    const { name, value } = event.target
    setPigForm((current) => ({ ...current, [name]: value }))
  }

  const handlePigPhotoChange = (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    setPigPhoto(file)
    setPigPhotoPreview(URL.createObjectURL(file))
  }

  const handleEditPigChange = (event) => {
    const { name, value } = event.target
    if (!selectedPig) return

    setEditPigDraft((current) => {
      const baseForm = current.pigId === String(selectedPig.id) ? current.form : pigFormFromRecord(selectedPig)

      return {
        ...current,
        pigId: String(selectedPig.id),
        form: { ...baseForm, [name]: value },
      }
    })
  }

  const handleEditPigPhotoChange = (event) => {
    const file = event.target.files?.[0]
    if (!file || !selectedPig) return

    setEditPigDraft((current) => ({
      ...current,
      pigId: String(selectedPig.id),
      form: current.pigId === String(selectedPig.id) ? current.form : pigFormFromRecord(selectedPig),
      photo: file,
      preview: URL.createObjectURL(file),
    }))
  }

  const handleOpenEditPig = () => {
    if (!selectedPig) return

    setEditPigDraft({
      pigId: String(selectedPig.id),
      form: pigFormFromRecord(selectedPig),
      photo: null,
      preview: "",
    })
    setIsEditModalOpen(true)
  }

  const handleCloseEditPig = () => {
    if (isUpdatingPig) return

    setIsEditModalOpen(false)
    if (!selectedPig) return

    setEditPigDraft({
      pigId: String(selectedPig.id),
      form: pigFormFromRecord(selectedPig),
      photo: null,
      preview: "",
    })
  }

  const handleMedicationChange = (event) => {
    const { name, value } = event.target
    setMedicationForm((current) => {
      if (name === "medicine_name") {
        const medication = availableMedications.find((item) => item["Nome comercial"] === value)

        if (!medication) {
          return {
            ...current,
            medicine_name: value,
            active_principle: "",
            route: "outra",
            withdrawal_until: "",
          }
        }

        return {
          ...current,
          medicine_name: medication["Nome comercial"],
          active_principle: isFilledMedicationValue(medication["Princípio ativo"]) ? medication["Princípio ativo"] : "",
          route: routeFromMedication(medication["Via administração"]),
          withdrawal_until: withdrawalDateFromMedication(medication.Carência, current.applied_at),
        }
      }

      if (name === "applied_at") {
        return {
          ...current,
          applied_at: value,
          withdrawal_until: selectedMedication
            ? withdrawalDateFromMedication(selectedMedication.Carência, value)
            : current.withdrawal_until,
        }
      }

      return { ...current, [name]: value }
    })
  }

  const handleSelectPig = (pigId) => {
    setSelectedPigId(String(pigId))
    setMedicationForm((current) => ({ ...current, pig: String(pigId) }))
  }

  const handleMedicationPigChange = (event) => {
    handleSelectPig(event.target.value)
  }

  const handleCreatePig = async (event) => {
    event.preventDefault()
    setIsSavingPig(true)
    setMessage("")

    try {
      const createdPig = await createPig(buildPigPayload(pigForm, pigPhoto))
      setPigs((current) => [...current, createdPig])
      handleSelectPig(createdPig.id)
      setPigForm(emptyPigForm)
      setPigPhoto(null)
      setPigPhotoPreview("")
      setMessage("Suino cadastrado com sucesso.")
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSavingPig(false)
    }
  }

  const handleUpdatePig = async (event) => {
    event.preventDefault()
    if (!selectedPig) return

    setIsUpdatingPig(true)
    setMessage("")

    try {
      const updatedPig = await updatePig(selectedPig.id, buildPigPayload(activeEditPigForm, activeEditPigPhoto))
      setPigs((current) => current.map((pig) => (pig.id === updatedPig.id ? updatedPig : pig)))
      setEditPigDraft({
        pigId: String(updatedPig.id),
        form: pigFormFromRecord(updatedPig),
        photo: null,
        preview: "",
      })
      setIsEditModalOpen(false)
      setMessage("Suíno atualizado com sucesso.")
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsUpdatingPig(false)
    }
  }

  const handleCreateMedication = async (event) => {
    event.preventDefault()
    setIsSavingMedication(true)
    setMessage("")

    const payload = Object.fromEntries(
      Object.entries(medicationForm).filter(([, value]) => value !== "")
    )

    try {
      const createdMedication = await createMedication(payload)
      setMedications((current) => [createdMedication, ...current])
      setMedicationForm((current) => ({
        ...emptyMedicationForm,
        pig: current.pig,
        applied_at: today,
      }))
      setMessage("Aplicacao registrada com sucesso.")
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSavingMedication(false)
    }
  }

  if (isLoading) {
    return (
      <main className="suinos-page">
        <section className="suinos-shell">
          <p className="suinos-message">Carregando suínos...</p>
        </section>
      </main>
    )
  }

  if (pigId) {
    if (!selectedPig) {
      return (
        <main className="suinos-page">
          <section className="suinos-shell">
            <Link to="/suinos" className="suinos-back">
              <ArrowLeft size={18} />
              Voltar aos suínos
            </Link>
            <p className="suinos-message">Suíno não encontrado.</p>
          </section>
        </main>
      )
    }

    return (
      <main className="suinos-page">
        <section className="suinos-shell">
          <Link to="/suinos" className="suinos-back">
            <ArrowLeft size={18} />
            Voltar aos suínos
          </Link>

          <header className="suinos-header suinos-detail-header">
            <div>
              <span className="suinos-kicker">Histórico do suíno</span>
              <h1>{selectedPig.name}</h1>
              <p>{selectedPig.tag || "Sem código"} · {selectedPig.status}</p>
            </div>
            {selectedPig.photo_url ? (
              <img src={selectedPig.photo_url} alt="" className="suinos-detail-photo" />
            ) : (
              <div className="suinos-header-icon">
                <UserRound size={34} strokeWidth={1.7} />
              </div>
            )}
          </header>

          {message && <p className="suinos-message">{message}</p>}

          <div className="suinos-detail-layout">
            <section className="suinos-panel">
              <div className="suinos-panel-title">
                <h2>Dados do animal</h2>
                <button type="button" className="suinos-icon-action" onClick={handleOpenEditPig} aria-label="Editar suíno">
                  <Pencil size={18} strokeWidth={1.8} />
                  Editar
                </button>
              </div>
              <dl className="suinos-detail-list">
                <div>
                  <dt>Raça / linhagem</dt>
                  <dd>{selectedPig.breed || "Não informada"}</dd>
                </div>
                <div>
                  <dt>Sexo</dt>
                  <dd>{selectedPig.sex ? selectedPig.sex : "Não informado"}</dd>
                </div>
                <div>
                  <dt>Fase</dt>
                  <dd>{displayOption(selectedPig.life_stage, lifeStageLabels)}</dd>
                </div>
                <div>
                  <dt>Porte</dt>
                  <dd>{displayOption(selectedPig.size_category, sizeLabels)}</dd>
                </div>
                <div>
                  <dt>Baia / lote</dt>
                  <dd>{selectedPig.pen || "Não informado"}</dd>
                </div>
                <div>
                  <dt>Origem</dt>
                  <dd>{selectedPig.origin || "Não informada"}</dd>
                </div>
                <div>
                  <dt>Nascimento</dt>
                  <dd>{selectedPig.birth_date || "Não informado"}</dd>
                </div>
                <div>
                  <dt>Peso</dt>
                  <dd>{selectedPig.weight_kg ? `${selectedPig.weight_kg} kg` : "Não informado"}</dd>
                </div>
                <div>
                  <dt>Observações</dt>
                  <dd>{selectedPig.notes || "Sem observações."}</dd>
                </div>
              </dl>
            </section>

            <section className="suinos-panel suinos-history-panel">
              <div className="suinos-panel-title">
                <h2>Histórico de medicações</h2>
                <span>{selectedPigMedications.length} registros</span>
              </div>

              <div className="suinos-timeline">
                {selectedPigMedications.length === 0 && <p className="suinos-empty">Nenhuma aplicação registrada para este suíno.</p>}
                {selectedPigMedications.map((record) => (
                  <article key={record.id}>
                    <time>{record.applied_at}</time>
                    <div>
                      <strong>{record.medicine_name}</strong>
                      <span>{record.active_principle || "Princípio ativo não informado"}</span>
                      <p>{record.dose || "Dose não informada"} · {record.route}</p>
                      {record.withdrawal_until && <small>Carência até {record.withdrawal_until}</small>}
                      {record.responsible && <small>Responsável: {record.responsible}</small>}
                      {record.notes && <p>{record.notes}</p>}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>

          {isEditModalOpen && (
            <div className="suinos-modal-backdrop" role="presentation" onMouseDown={handleCloseEditPig}>
              <section
                className="suinos-modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="suinos-edit-title"
                onMouseDown={(event) => event.stopPropagation()}
              >
                <div className="suinos-modal-header">
                  <div>
                    <span className="suinos-kicker">Ficha cadastral</span>
                    <h2 id="suinos-edit-title">Editar suíno</h2>
                  </div>
                  <button type="button" className="suinos-modal-close" onClick={handleCloseEditPig} aria-label="Fechar edição">
                    <X size={20} strokeWidth={1.8} />
                  </button>
                </div>

                <form className="suinos-form" onSubmit={handleUpdatePig}>
                  <label className="suinos-photo-field">
                    <span className="suinos-photo-preview">
                      {activeEditPigPhotoPreview ? (
                        <img src={activeEditPigPhotoPreview} alt="" />
                      ) : selectedPig.photo_url ? (
                        <img src={selectedPig.photo_url} alt="" />
                      ) : (
                        <ImagePlus size={24} strokeWidth={1.7} />
                      )}
                    </span>
                    <span>
                      <strong>Foto do suíno</strong>
                      <small>Troque a imagem usada para identificar este animal.</small>
                    </span>
                    <input type="file" accept="image/*" onChange={handleEditPigPhotoChange} />
                  </label>

                  <div className="suinos-form-row">
                    <label>
                      <span>Nome ou identificação</span>
                      <input name="name" value={activeEditPigForm.name} onChange={handleEditPigChange} required />
                    </label>
                    <label>
                      <span>Brinco / código</span>
                      <input name="tag" value={activeEditPigForm.tag} onChange={handleEditPigChange} />
                    </label>
                  </div>

                  <div className="suinos-form-row">
                    <label>
                      <span>Raça / linhagem</span>
                      <input name="breed" value={activeEditPigForm.breed} onChange={handleEditPigChange} />
                    </label>
                    <label>
                      <span>Sexo</span>
                      <select name="sex" value={activeEditPigForm.sex} onChange={handleEditPigChange}>
                        <option value="">Selecione</option>
                        <option value="macho">Macho</option>
                        <option value="femea">Fêmea</option>
                      </select>
                    </label>
                  </div>

                  <div className="suinos-form-row">
                    <label>
                      <span>Fase</span>
                      <select name="life_stage" value={activeEditPigForm.life_stage} onChange={handleEditPigChange}>
                        <option value="">Selecione</option>
                        {Object.entries(lifeStageLabels).map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Porte</span>
                      <select name="size_category" value={activeEditPigForm.size_category} onChange={handleEditPigChange}>
                        <option value="">Selecione</option>
                        {Object.entries(sizeLabels).map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="suinos-form-row">
                    <label>
                      <span>Baia / lote</span>
                      <input name="pen" value={activeEditPigForm.pen} onChange={handleEditPigChange} />
                    </label>
                    <label>
                      <span>Origem</span>
                      <input name="origin" value={activeEditPigForm.origin} onChange={handleEditPigChange} />
                    </label>
                  </div>

                  <div className="suinos-form-row">
                    <label>
                      <span>Nascimento</span>
                      <input type="date" name="birth_date" value={activeEditPigForm.birth_date} onChange={handleEditPigChange} />
                    </label>
                    <label>
                      <span>Peso kg</span>
                      <input type="number" step="0.01" name="weight_kg" value={activeEditPigForm.weight_kg} onChange={handleEditPigChange} />
                    </label>
                  </div>

                  <label>
                    <span>Status</span>
                    <select name="status" value={activeEditPigForm.status} onChange={handleEditPigChange}>
                      <option value="ativo">Ativo</option>
                      <option value="tratamento">Em tratamento</option>
                      <option value="vendido">Vendido</option>
                      <option value="obito">Óbito</option>
                    </select>
                  </label>

                  <label>
                    <span>Observações</span>
                    <textarea name="notes" value={activeEditPigForm.notes} onChange={handleEditPigChange} rows="3" />
                  </label>

                  <div className="suinos-modal-actions">
                    <button type="button" className="suinos-secondary-button" onClick={handleCloseEditPig} disabled={isUpdatingPig}>
                      Cancelar
                    </button>
                    <button type="submit" disabled={isUpdatingPig}>
                      <Save size={18} strokeWidth={1.8} />
                      {isUpdatingPig ? "Salvando..." : "Salvar alterações"}
                    </button>
                  </div>
                </form>
              </section>
            </div>
          )}
        </section>
      </main>
    )
  }

  return (
    <main className="suinos-page">
      <section className="suinos-shell">
        <header className="suinos-header">
          <div>
            <span className="suinos-kicker">Controle sanitário</span>
            <h1>Suínos cadastrados</h1>
            <p>Registre cada animal e acompanhe medicamentos aplicados por data.</p>
          </div>
          <div className="suinos-header-icon">
            <ClipboardList size={34} strokeWidth={1.7} />
          </div>
        </header>

        <div className="suinos-stats">
          <article>
            <UserRound size={20} strokeWidth={1.7} />
            <span>Total de suínos</span>
            <strong>{dashboard.totalPigs}</strong>
          </article>
          <article>
            <Syringe size={20} strokeWidth={1.7} />
            <span>Aplicações registradas</span>
            <strong>{dashboard.medicationCount}</strong>
          </article>
          <article>
            <CalendarDays size={20} strokeWidth={1.7} />
            <span>Aplicações no mês</span>
            <strong>{dashboard.monthMedicationCount}</strong>
          </article>
          <article>
            <Plus size={20} strokeWidth={1.7} />
            <span>Em tratamento</span>
            <strong>{dashboard.treatmentCount}</strong>
          </article>
        </div>

        {message && <p className="suinos-message">{message}</p>}

        <div className="suinos-layout">
          <aside className="suinos-panel">
            <h2>Cadastrar suíno</h2>
            <form className="suinos-form" onSubmit={handleCreatePig}>
              <label className="suinos-photo-field">
                <span className="suinos-photo-preview">
                  {pigPhotoPreview ? <img src={pigPhotoPreview} alt="" /> : <ImagePlus size={24} strokeWidth={1.7} />}
                </span>
                <span>
                  <strong>Imagem do suíno</strong>
                  <small>Selecione uma foto para identificar o animal.</small>
                </span>
                <input type="file" accept="image/*" onChange={handlePigPhotoChange} />
              </label>
              <label>
                <span>Nome ou identificação</span>
                <input name="name" value={pigForm.name} onChange={handlePigChange} required />
              </label>
              <label>
                <span>Brinco / código</span>
                <input name="tag" value={pigForm.tag} onChange={handlePigChange} />
              </label>
              <label>
                <span>Raça / linhagem</span>
                <input name="breed" value={pigForm.breed} onChange={handlePigChange} />
              </label>
              <div className="suinos-form-row">
                <label>
                  <span>Fase</span>
                  <select name="life_stage" value={pigForm.life_stage} onChange={handlePigChange}>
                    <option value="">Selecione</option>
                    {Object.entries(lifeStageLabels).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Porte</span>
                  <select name="size_category" value={pigForm.size_category} onChange={handlePigChange}>
                    <option value="">Selecione</option>
                    {Object.entries(sizeLabels).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="suinos-form-row">
                <label>
                  <span>Sexo</span>
                  <select name="sex" value={pigForm.sex} onChange={handlePigChange}>
                    <option value="">Selecione</option>
                    <option value="macho">Macho</option>
                    <option value="femea">Fêmea</option>
                  </select>
                </label>
                <label>
                  <span>Status</span>
                  <select name="status" value={pigForm.status} onChange={handlePigChange}>
                    <option value="ativo">Ativo</option>
                    <option value="tratamento">Em tratamento</option>
                    <option value="vendido">Vendido</option>
                    <option value="obito">Óbito</option>
                  </select>
                </label>
              </div>
              <div className="suinos-form-row">
                <label>
                  <span>Baia / lote</span>
                  <input name="pen" value={pigForm.pen} onChange={handlePigChange} />
                </label>
                <label>
                  <span>Origem</span>
                  <input name="origin" value={pigForm.origin} onChange={handlePigChange} />
                </label>
              </div>
              <div className="suinos-form-row suinos-form-row-spaced">
                <label>
                  <span>Nascimento</span>
                  <input type="date" name="birth_date" value={pigForm.birth_date} onChange={handlePigChange} />
                </label>
                <label>
                  <span>Peso kg</span>
                  <input type="number" step="0.01" name="weight_kg" value={pigForm.weight_kg} onChange={handlePigChange} />
                </label>
              </div>
              <label>
                <span>Observações</span>
                <textarea name="notes" value={pigForm.notes} onChange={handlePigChange} rows="3" />
              </label>
              <button type="submit" disabled={isSavingPig}>
                {isSavingPig ? "Salvando..." : "Cadastrar suíno"}
              </button>
            </form>
          </aside>

          <section className="suinos-panel suinos-list-panel">
            <div className="suinos-panel-title">
              <h2>Meus suínos</h2>
              <span>{pigs.length} cadastrados</span>
            </div>

            <div className="suinos-list">
              {pigs.length === 0 && <p className="suinos-empty">Nenhum suíno cadastrado ainda.</p>}
              {pigs.map((pig) => (
                <button
                  key={pig.id}
                  type="button"
                  className={String(selectedPigId) === String(pig.id) ? "suinos-pig-card suinos-pig-card-active" : "suinos-pig-card"}
                  onClick={() => navigate(`/suinos/${pig.id}`)}
                >
                  {pig.photo_url && <img src={pig.photo_url} alt="" className="suinos-pig-thumb" />}
                  <strong>{pig.name}</strong>
                  <span>{pig.tag || "Sem código"} · {pig.status}</span>
                  <small>{pig.medications_count || 0} aplicações</small>
                </button>
              ))}
            </div>
          </section>

          <section className="suinos-panel suinos-med-panel">
            <div className="suinos-panel-title">
              <h2>Medicações</h2>
              <span>{selectedPig ? selectedPig.name : "Selecione um suíno"}</span>
            </div>

            <form className="suinos-form" onSubmit={handleCreateMedication}>
              <label>
                <span>Suíno</span>
                <select name="pig" value={medicationForm.pig} onChange={handleMedicationPigChange} required>
                  <option value="">Selecione o suíno</option>
                  {pigs.map((pig) => (
                    <option key={pig.id} value={pig.id}>{pig.name}</option>
                  ))}
                </select>
              </label>
              <div className="suinos-form-row">
                <label>
                  <span>Medicamento</span>
                  <select name="medicine_name" value={medicationForm.medicine_name} onChange={handleMedicationChange} required>
                    <option value="">Selecione</option>
                    {availableMedications.map((medication) => (
                      <option key={medication["Nome comercial"]} value={medication["Nome comercial"]}>
                        {medication["Nome comercial"]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Princípio ativo</span>
                  <input name="active_principle" value={medicationForm.active_principle} onChange={handleMedicationChange} />
                </label>
              </div>
              <div className="suinos-form-row">
                <label>
                  <span>Dose</span>
                  <input name="dose" value={medicationForm.dose} onChange={handleMedicationChange} />
                </label>
                <label>
                  <span>Via</span>
                  <select name="route" value={medicationForm.route} onChange={handleMedicationChange}>
                    <option value="oral">Oral</option>
                    <option value="intramuscular">Intramuscular</option>
                    <option value="subcutanea">Subcutânea</option>
                    <option value="topica">Tópica</option>
                    <option value="outra">Outra</option>
                  </select>
                </label>
              </div>
              <div className="suinos-form-row">
                <label>
                  <span>Data de aplicação</span>
                  <input type="date" name="applied_at" value={medicationForm.applied_at} onChange={handleMedicationChange} required />
                </label>
                <label>
                  <span>Carência até</span>
                  <input type="date" name="withdrawal_until" value={medicationForm.withdrawal_until} onChange={handleMedicationChange} />
                </label>
              </div>
              <label>
                <span>Responsável</span>
                <input name="responsible" value={medicationForm.responsible} onChange={handleMedicationChange} />
              </label>
              <label>
                <span>Observações</span>
                <textarea name="notes" value={medicationForm.notes} onChange={handleMedicationChange} rows="3" />
              </label>
              <button type="submit" disabled={isSavingMedication || pigs.length === 0}>
                {isSavingMedication ? "Registrando..." : "Registrar aplicação"}
              </button>
            </form>

            <div className="suinos-med-list">
              {selectedPigMedications.length === 0 && <p className="suinos-empty">Nenhuma aplicação para este suíno.</p>}
              {selectedPigMedications.map((record) => (
                <article key={record.id}>
                  <strong>{record.medicine_name}</strong>
                  <span>{record.applied_at} · {record.dose || "Dose não informada"} · {record.route}</span>
                  {record.withdrawal_until && <small>Carência até {record.withdrawal_until}</small>}
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  )
}

export default Suinos
