import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Building2, Camera, Edit3, LayoutDashboard, LogOut, Mail, MapPin, Phone, Save, ShieldCheck, Syringe, User, X } from "lucide-react"
import { clearAuth, getAuth, getCurrentUser, logoutUser, saveAuth, updateCurrentUser } from "../../services/auth"
import { listMedications, listPigs } from "../../services/suinos"
import "./Perfil.css"

const userTypeLabels = {
  padrao: "Padrão",
  produtor: "Produtor",
  veterinario: "Veterinario",
  estudante: "Estudante",
  pesquisador: "Pesquisador",
}

const brazilStates = [
  { value: "AC", label: "Acre" },
  { value: "AL", label: "Alagoas" },
  { value: "AP", label: "Amapá" },
  { value: "AM", label: "Amazonas" },
  { value: "BA", label: "Bahia" },
  { value: "CE", label: "Ceará" },
  { value: "DF", label: "Distrito Federal" },
  { value: "ES", label: "Espírito Santo" },
  { value: "GO", label: "Goiás" },
  { value: "MA", label: "Maranhão" },
  { value: "MT", label: "Mato Grosso" },
  { value: "MS", label: "Mato Grosso do Sul" },
  { value: "MG", label: "Minas Gerais" },
  { value: "PA", label: "Pará" },
  { value: "PB", label: "Paraíba" },
  { value: "PR", label: "Paraná" },
  { value: "PE", label: "Pernambuco" },
  { value: "PI", label: "Piauí" },
  { value: "RJ", label: "Rio de Janeiro" },
  { value: "RN", label: "Rio Grande do Norte" },
  { value: "RS", label: "Rio Grande do Sul" },
  { value: "RO", label: "Rondônia" },
  { value: "RR", label: "Roraima" },
  { value: "SC", label: "Santa Catarina" },
  { value: "SP", label: "São Paulo" },
  { value: "SE", label: "Sergipe" },
  { value: "TO", label: "Tocantins" },
]

function buildFormState(user) {
  const profile = user?.profile || {}

  return {
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    user_type: profile.user_type || "padrao",
    phone: profile.phone || "",
    institution: profile.institution || "",
    role: profile.role || "",
    crmv: profile.crmv || "",
    city: profile.city || "",
    state: profile.state || "",
    photo: null,
  }
}

function Perfil() {
  const [user, setUser] = useState(getAuth()?.user || null)
  const [form, setForm] = useState(buildFormState(getAuth()?.user))
  const [isEditing, setIsEditing] = useState(false)
  const [message, setMessage] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [photoPreview, setPhotoPreview] = useState(getAuth()?.user?.profile?.photo_url || "")
  const [cityOptions, setCityOptions] = useState([])
  const [isLoadingCities, setIsLoadingCities] = useState(false)
  const [activePanel, setActivePanel] = useState("perfil")
  const [dashboard, setDashboard] = useState({ pigs: [], medications: [] })
  const navigate = useNavigate()

  useEffect(() => {
    let isActive = true

    async function loadProfile() {
      if (!getAuth()?.token) {
        navigate("/login")
        return
      }

      try {
        const currentUser = await getCurrentUser()
        if (!isActive) return
        setUser(currentUser)
        setForm(buildFormState(currentUser))
        setPhotoPreview(currentUser.profile?.photo_url || "")
        saveAuth({ token: getAuth()?.token, user: currentUser })
        const [pigs, medications] = await Promise.all([listPigs(), listMedications()])
        if (!isActive) return
        setDashboard({ pigs, medications })
      } catch {
        clearAuth()
        navigate("/login")
      } finally {
        if (isActive) setIsLoading(false)
      }
    }

    loadProfile()

    return () => {
      isActive = false
    }
  }, [navigate])

  useEffect(() => {
    if (!isEditing || !form.state) {
      return
    }

    const controller = new AbortController()

    async function loadCities() {
      setIsLoadingCities(true)

      try {
        const response = await fetch(
          `https://servicodados.ibge.gov.br/api/v1/localidades/estados/${form.state}/municipios?orderBy=nome`,
          { signal: controller.signal }
        )
        const data = await response.json()
        setCityOptions(data.map((city) => city.nome))
      } catch (error) {
        if (error.name !== "AbortError") {
          setCityOptions([])
          setMessage("Nao foi possivel carregar as cidades dessa UF agora.")
        }
      } finally {
        if (!controller.signal.aborted) setIsLoadingCities(false)
      }
    }

    loadCities()

    return () => controller.abort()
  }, [form.state, isEditing])

  const handleLogout = async () => {
    setMessage("")
    await logoutUser()
    navigate("/login")
  }

  const handleChange = (event) => {
    const { name, value } = event.target
    if (name === "state") setCityOptions([])

    setForm((current) => ({
      ...current,
      [name]: name === "state" ? value.toUpperCase().slice(0, 2) : value,
      ...(name === "state" ? { city: "" } : {}),
    }))
  }

  const handlePhotoChange = (event) => {
    const file = event.target.files?.[0]
    if (!file) return

    setForm((current) => ({ ...current, photo: file }))
    setPhotoPreview(URL.createObjectURL(file))
  }

  const handleCancelEdit = () => {
    setForm(buildFormState(user))
    setPhotoPreview(user?.profile?.photo_url || "")
    setIsEditing(false)
    setMessage("")
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage("")
    setIsSaving(true)

    const payload = new FormData()
    Object.entries(form).forEach(([key, value]) => {
      if (key === "photo") {
        if (value) payload.append(key, value)
        return
      }
      if (key === "user_type" && value === "padrao") return
      payload.append(key, value)
    })

    try {
      const updatedUser = await updateCurrentUser(payload)
      setUser(updatedUser)
      setForm(buildFormState(updatedUser))
      setPhotoPreview(updatedUser.profile?.photo_url || "")
      setIsEditing(false)
      setMessage("Perfil atualizado com sucesso.")
    } catch (error) {
      setMessage(error.message)
    } finally {
      setIsSaving(false)
    }
  }

  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ")
  const profile = user?.profile || {}
  const displayPhoto = photoPreview || profile.photo_url
  const profileRole = [profile.institution, profile.role].filter(Boolean).join(" · ") || userTypeLabels[profile.user_type] || "Perfil padrão"
  const locationLabel = [profile.city, profile.state].filter(Boolean).join(" - ") || "Nao informado"
  const currentMonth = new Date().toISOString().slice(0, 7)
  const dashboardStats = {
    pigs: dashboard.pigs.length,
    treatments: dashboard.pigs.filter((pig) => pig.status === "tratamento").length,
    medications: dashboard.medications.length,
    monthMedications: dashboard.medications.filter((record) => record.applied_at?.startsWith(currentMonth)).length,
  }
  const recentMedications = dashboard.medications.slice(0, 5)

  if (isLoading) {
    return (
      <main className="perfil-page">
        <section className="perfil-card">
          <p className="perfil-loading">Carregando perfil...</p>
        </section>
      </main>
    )
  }

  return (
    <main className="perfil-page">
      <section className="perfil-card">
        <div className="perfil-header">
          <span className="perfil-avatar">
            {displayPhoto ? (
              <img src={displayPhoto} alt="" />
            ) : (
              <User size={34} strokeWidth={1.7} />
            )}
          </span>
          <div>
            <span className="perfil-kicker">Minha conta</span>
            <h1>{fullName || user?.username || "Perfil"}</h1>
            <p>{profileRole}</p>
          </div>
        </div>

        <div className="perfil-tabs">
          <button
            type="button"
            className={activePanel === "dashboard" ? "perfil-tab perfil-tab-active" : "perfil-tab"}
            onClick={() => setActivePanel("dashboard")}
          >
            <LayoutDashboard size={18} strokeWidth={1.7} />
            Dashboard
          </button>
          <button
            type="button"
            className={activePanel === "perfil" ? "perfil-tab perfil-tab-active" : "perfil-tab"}
            onClick={() => setActivePanel("perfil")}
          >
            <User size={18} strokeWidth={1.7} />
            Perfil
          </button>
        </div>

        {activePanel === "dashboard" ? (
          <div className="perfil-dashboard">
            <div className="perfil-dashboard-grid">
              <article>
                <User size={20} strokeWidth={1.7} />
                <span>Suínos cadastrados</span>
                <strong>{dashboardStats.pigs}</strong>
              </article>
              <article>
                <ShieldCheck size={20} strokeWidth={1.7} />
                <span>Em tratamento</span>
                <strong>{dashboardStats.treatments}</strong>
              </article>
              <article>
                <Syringe size={20} strokeWidth={1.7} />
                <span>Aplicações totais</span>
                <strong>{dashboardStats.medications}</strong>
              </article>
              <article>
                <MapPin size={20} strokeWidth={1.7} />
                <span>Aplicações no mês</span>
                <strong>{dashboardStats.monthMedications}</strong>
              </article>
            </div>

            <div className="perfil-dashboard-panel">
              <div>
                <h2>Medicações recentes</h2>
                <p>Últimos registros lançados na área de suínos.</p>
              </div>
              <Link to="/suinos" className="perfil-secondary">Abrir cadastro de suínos</Link>
            </div>

            <div className="perfil-recent-list">
              {recentMedications.length === 0 && <p className="perfil-loading">Nenhuma medicação registrada ainda.</p>}
              {recentMedications.map((record) => (
                <article key={record.id}>
                  <strong>{record.medicine_name}</strong>
                  <span>{record.pig_name} · {record.applied_at} · {record.dose || "Dose não informada"}</span>
                </article>
              ))}
            </div>
          </div>
        ) : isEditing ? (
          <form className="perfil-editor" onSubmit={handleSubmit}>
            <label className="perfil-photo-field">
              <span className="perfil-photo-preview">
                {displayPhoto ? <img src={displayPhoto} alt="" /> : <Camera size={26} strokeWidth={1.7} />}
              </span>
              <span>
                <strong>Foto de perfil</strong>
                <small>Escolha uma imagem para aparecer na sua conta.</small>
              </span>
              <input type="file" accept="image/*" onChange={handlePhotoChange} />
            </label>

            <div className="perfil-form-grid">
              <label className="perfil-field">
                <span>Nome</span>
                <input name="first_name" value={form.first_name} onChange={handleChange} />
              </label>
              <label className="perfil-field">
                <span>Sobrenome</span>
                <input name="last_name" value={form.last_name} onChange={handleChange} />
              </label>
              <label className="perfil-field">
                <span>Tipo de usuario</span>
                <select
                  name="user_type"
                  value={form.user_type === "padrao" ? "" : form.user_type}
                  onChange={handleChange}
                >
                  <option value="" disabled>Selecione um tipo</option>
                  <option value="produtor">Produtor</option>
                  <option value="veterinario">Veterinario</option>
                  <option value="estudante">Estudante</option>
                  <option value="pesquisador">Pesquisador</option>
                </select>
              </label>
              <label className="perfil-field">
                <span>Telefone</span>
                <input name="phone" value={form.phone} onChange={handleChange} />
              </label>
              <label className="perfil-field">
                <span>Instituicao</span>
                <input name="institution" value={form.institution} onChange={handleChange} />
              </label>
              <label className="perfil-field">
                <span>Funcao</span>
                <input name="role" value={form.role} onChange={handleChange} />
              </label>
              <label className="perfil-field">
                <span>CRMV</span>
                <input name="crmv" value={form.crmv} onChange={handleChange} />
              </label>
              <label className="perfil-field">
                <span>UF</span>
                <select name="state" value={form.state} onChange={handleChange}>
                  <option value="">Selecione a UF</option>
                  {brazilStates.map((state) => (
                    <option key={state.value} value={state.value}>
                      {state.value} - {state.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="perfil-field">
                <span>Cidade</span>
                <select name="city" value={form.city} onChange={handleChange} disabled={!form.state || isLoadingCities}>
                  <option value="">
                    {isLoadingCities ? "Carregando cidades..." : "Selecione a cidade"}
                  </option>
                  {form.city && !cityOptions.includes(form.city) && (
                    <option value={form.city}>{form.city}</option>
                  )}
                  {cityOptions.map((city) => (
                    <option key={city} value={city}>{city}</option>
                  ))}
                </select>
              </label>
            </div>
          </form>
        ) : (
          <article className="perfil-public-card">
            <div className="perfil-public-lines">
              <div>
                <strong><ShieldCheck size={16} strokeWidth={1.8} /> Tipo de Conta:</strong>
                <span>{userTypeLabels[profile.user_type] || "Padrão"}</span>
              </div>
              <div>
                <strong><Building2 size={16} strokeWidth={1.8} /> Instituicao:</strong>
                <span>{profile.institution || "Nao informado"}</span>
              </div>
              <div>
                <strong><User size={16} strokeWidth={1.8} /> Funcao:</strong>
                <span>{profile.role || "Nao informado"}</span>
              </div>
              <div>
                <strong><MapPin size={16} strokeWidth={1.8} /> Localizacao:</strong>
                <span>{locationLabel}</span>
              </div>
              <div>
                <strong><Phone size={16} strokeWidth={1.8} /> Telefone:</strong>
                <span>{profile.phone || "Nao informado"}</span>
              </div>
              <div>
                <strong><Mail size={16} strokeWidth={1.8} /> E-mail:</strong>
                <span>{user?.email || "Nao informado"}</span>
              </div>
            </div>
          </article>
        )}

        {message && <p className="perfil-message">{message}</p>}

        <div className="perfil-actions">
          {activePanel === "dashboard" ? (
            <>
              <Link to="/" className="perfil-secondary">Voltar para o inicio</Link>
              <Link to="/suinos" className="perfil-logout">Gerenciar suínos</Link>
            </>
          ) : isEditing ? (
            <>
              <button type="button" className="perfil-secondary" onClick={handleCancelEdit}>
                <X size={18} strokeWidth={1.7} />
                Cancelar
              </button>
              <button type="button" className="perfil-logout" onClick={handleSubmit} disabled={isSaving}>
                <Save size={18} strokeWidth={1.7} />
                {isSaving ? "Salvando..." : "Salvar perfil"}
              </button>
            </>
          ) : (
            <>
              <Link to="/" className="perfil-secondary">Voltar para o inicio</Link>
              <button type="button" className="perfil-secondary" onClick={() => setIsEditing(true)}>
                <Edit3 size={18} strokeWidth={1.7} />
                Editar perfil
              </button>
              <button type="button" className="perfil-logout" onClick={handleLogout}>
                <LogOut size={18} strokeWidth={1.7} />
                Sair da conta
              </button>
            </>
          )}
        </div>
      </section>
    </main>
  )
}

export default Perfil
