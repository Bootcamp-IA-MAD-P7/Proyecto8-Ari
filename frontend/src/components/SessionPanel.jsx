import { useState } from 'react'
import ErrorBanner from './ErrorBanner.jsx'
import ResultSummary from './ResultSummary.jsx'
import OpenSessionForm from './forms/OpenSessionForm.jsx'
import TabularForm from './forms/TabularForm.jsx'
import ReferralForm from './forms/ReferralForm.jsx'
import ImageUploadForm from './forms/ImageUploadForm.jsx'
import CloseActions from './forms/CloseActions.jsx'
import { STATE_UI } from '../domain/sessionStates.js'
import './SessionPanel.css'

// Detail panel: reacts to `session.estado` per the section 3 map — this
// switch IS the render-condicional the spec calls "la ley". Every form
// here calls its handler and nothing else; the POST-then-GET pattern and
// id_sesion tracking live one level up, in App.jsx.
function SessionPanel({
  session,
  error,
  loading,
  onOpenSession,
  onClassifyTabular,
  onRefer,
  onClassifyImage,
  onCloseSession,
}) {
  // Local-only UI toggle (not session state): whether the "derivar a
  // imagen" textarea is showing instead of the three-way choice.
  const [showReferral, setShowReferral] = useState(false)

  if (!session) {
    return (
      <section className="session-panel">
        <h2>Ninguna sesión activa</h2>
        <p>Abrí una sesión con la ficha del paciente para empezar.</p>
        <ErrorBanner error={error} />
        <OpenSessionForm onSubmit={onOpenSession} loading={loading} fieldErrors={error?.fieldErrors} />
      </section>
    )
  }

  const { heading, description } = STATE_UI[session.estado]

  return (
    <section className="session-panel">
      <p className="session-panel__meta">
        Paciente <strong>{session.id_paciente}</strong> · sesión <code>{session.id_sesion}</code>
      </p>

      <h2>{heading}</h2>
      <p>{description}</p>

      <ErrorBanner error={error} />
      {loading && <p className="session-panel__loading">Enviando…</p>}

      {session.resultado_tabular && (
        <ResultSummary title="Resultado tabular" result={session.resultado_tabular} />
      )}
      {session.resultado_imagen && (
        <ResultSummary title="Resultado imagen" result={session.resultado_imagen} />
      )}

      {session.estado === 'abierta' && (
        <TabularForm onSubmit={onClassifyTabular} loading={loading} fieldErrors={error?.fieldErrors} />
      )}

      {session.estado === 'clasificada_tabular' && !showReferral && (
        <div className="session-panel__actions">
          <button type="button" onClick={() => setShowReferral(true)} disabled={loading}>
            Derivar a imagen
          </button>
          <CloseActions onClose={onCloseSession} loading={loading} />
        </div>
      )}
      {session.estado === 'clasificada_tabular' && showReferral && (
        <ReferralForm
          onSubmit={onRefer}
          loading={loading}
          fieldErrors={error?.fieldErrors}
          onCancel={() => setShowReferral(false)}
        />
      )}

      {session.estado === 'derivada_imagen' && (
        <ImageUploadForm
          onSubmit={onClassifyImage}
          loading={loading}
          fieldErrors={error?.fieldErrors}
        />
      )}

      {session.estado === 'clasificada_imagen' && (
        <CloseActions onClose={onCloseSession} loading={loading} />
      )}

      {session.estado === 'cerrada' && (
        <div className="session-panel__closed">
          <p>
            <strong>Motivo de derivación:</strong> {session.motivo_derivacion ?? '—'}
          </p>
          <p>
            <strong>Decisión final:</strong> {session.decision_final}
          </p>
          <p className="session-panel__timestamps">
            Creada {session.creada_en} · actualizada {session.actualizada_en}
          </p>
        </div>
      )}
    </section>
  )
}

export default SessionPanel
