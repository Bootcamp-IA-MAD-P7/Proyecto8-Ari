import './forms.css'

// POST /sesiones/{id}/cierre body: { decision_final }, one of "alta" or
// "derivar_especialista" (reconocimiento_backend.md section 8). Used from
// both clasificada_tabular (alta directa) and clasificada_imagen.
function CloseActions({ onClose, loading }) {
  return (
    <div className="form__button-row">
      <button type="button" onClick={() => onClose('alta')} disabled={loading}>
        Alta
      </button>
      <button
        type="button"
        className="form__secondary"
        onClick={() => onClose('derivar_especialista')}
        disabled={loading}
      >
        Derivar a especialista
      </button>
    </div>
  )
}

export default CloseActions
