import { useState } from 'react'
import './forms.css'

// POST /sesiones/{id}/derivacion body: { motivo_derivacion }, 1-500 chars
// (reconocimiento_backend.md section 8). Empty submit is blocked
// client-side as UX — the server rejects it with 422 either way.
const MAX_LENGTH = 500

function ReferralForm({ onSubmit, loading, fieldErrors, onCancel }) {
  const [motivo, setMotivo] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    if (!motivo.trim()) return
    onSubmit(motivo.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="form">
      <label htmlFor="motivo_derivacion">Motivo de derivación</label>
      <textarea
        id="motivo_derivacion"
        value={motivo}
        maxLength={MAX_LENGTH}
        onChange={(event) => setMotivo(event.target.value)}
        disabled={loading}
        required
      />
      <p className="char-counter">
        {motivo.length}/{MAX_LENGTH}
      </p>
      {fieldErrors?.motivo_derivacion && (
        <p className="field-error">{fieldErrors.motivo_derivacion}</p>
      )}

      <div className="form__button-row">
        <button type="submit" disabled={loading || !motivo.trim()}>
          Derivar a imagen
        </button>
        <button type="button" className="form__secondary" onClick={onCancel} disabled={loading}>
          Cancelar
        </button>
      </div>
    </form>
  )
}

export default ReferralForm
