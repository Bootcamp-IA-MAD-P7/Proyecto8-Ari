import './forms.css'

// POST /sesiones/{id}/cierre body: { decision_final }, one of "alta" or
// "derivar_especialista" (reconocimiento_backend.md section 8). Used from
// both clasificada_tabular (alta directa) and clasificada_imagen. Both
// options carry the same `.decision-button` weight on purpose — the
// screen must not lean the clinical decision one way (spec_front.md
// section 7).
function CloseActions({ onClose, loading }) {
  return (
    <div className="decision-button-row">
      <button type="button" className="decision-button" onClick={() => onClose('alta')} disabled={loading}>
        Alta
      </button>
      <button
        type="button"
        className="decision-button"
        onClick={() => onClose('derivar_especialista')}
        disabled={loading}
      >
        Derivar a especialista
      </button>
    </div>
  )
}

export default CloseActions
