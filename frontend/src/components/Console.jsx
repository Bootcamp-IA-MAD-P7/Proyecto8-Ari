import Stepper from './Stepper.jsx'
import SessionPanel from './SessionPanel.jsx'
import TopBar from './TopBar.jsx'
import './Console.css'

// Master-detail shell (spec_front.md section 3). Master = stepper, in
// solo-lectura read-only progress; detail = the state-reactive panel.
// The server is the only source of truth for `estado` — this component
// takes it as a prop and renders, it never counts its own steps. Purely
// a layout/prop-passthrough component: no state, no API calls.
function Console({
  session,
  error,
  loading,
  onOpenSession,
  onClassifyTabular,
  onRefer,
  onClassifyImage,
  onCloseSession,
}) {
  return (
    <div className="console">
      <TopBar />
      <div className="console__body">
        <aside className="console__master">
          <Stepper currentState={session?.estado ?? null} />
        </aside>
        <main className="console__detail">
          <SessionPanel
            session={session}
            error={error}
            loading={loading}
            onOpenSession={onOpenSession}
            onClassifyTabular={onClassifyTabular}
            onRefer={onRefer}
            onClassifyImage={onClassifyImage}
            onCloseSession={onCloseSession}
          />
        </main>
      </div>
    </div>
  )
}

export default Console
