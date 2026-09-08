import { STATE_UI } from '../domain/sessionStates.js'
import './SessionPanel.css'

// Detail panel: reacts to `session.estado` per the section 3 map. No form
// logic yet (Block 3) — actions render as inert placeholders so the shell
// visibly reacts to state without doing anything real.
function SessionPanel({ session }) {
  if (!session) {
    return (
      <section className="session-panel session-panel--empty">
        <h2>Ninguna sesión activa</h2>
        <p>Abrí una sesión con la ficha del paciente para empezar.</p>
      </section>
    )
  }

  const { heading, description, actions } = STATE_UI[session.estado]

  return (
    <section className="session-panel">
      <p className="session-panel__meta">
        Paciente <strong>{session.id_paciente}</strong> · sesión{' '}
        <code>{session.id_sesion}</code>
      </p>

      <h2>{heading}</h2>
      <p>{description}</p>

      {actions.length > 0 && (
        <div className="session-panel__actions">
          {actions.map((action) => (
            <button key={action} type="button" disabled>
              {action}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

export default SessionPanel
