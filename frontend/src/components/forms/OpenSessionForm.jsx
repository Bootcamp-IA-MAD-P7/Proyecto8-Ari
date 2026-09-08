import { useState } from 'react'
import './forms.css'

// POST /sesiones body: { id_paciente } (reconocimiento_backend.md
// section 5). Required, non-empty string — the `required` attribute is a
// UX guard only, the server is still the judge.
function OpenSessionForm({ onSubmit, loading, fieldErrors }) {
  const [idPaciente, setIdPaciente] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    if (!idPaciente.trim()) return
    onSubmit(idPaciente.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="form">
      <label htmlFor="id_paciente">ID de paciente</label>
      <input
        id="id_paciente"
        type="text"
        value={idPaciente}
        onChange={(event) => setIdPaciente(event.target.value)}
        required
        disabled={loading}
      />
      {fieldErrors?.id_paciente && <p className="field-error">{fieldErrors.id_paciente}</p>}

      <button type="submit" disabled={loading || !idPaciente.trim()}>
        Abrir sesión
      </button>
    </form>
  )
}

export default OpenSessionForm
