import { useState } from 'react'
import Console from './components/Console.jsx'
import { SESSION_STATES } from './domain/sessionStates.js'
import './App.css'

// TEMPORARY, Block 2 checkpoint only. Builds a fake SesionOut-shaped
// object so Console's conditional render can be checked against every
// state without the real API wiring, which lands in Block 3 (POST-then-
// GET pattern, real id_sesion). Not real session data — never PHI.
function buildDevPreviewSession(estado) {
  if (estado === null) return null
  return {
    id_sesion: '00000000-0000-0000-0000-000000000000',
    id_paciente: 'PREVIEW',
    estado,
  }
}

function App() {
  const [devState, setDevState] = useState(null)
  const session = buildDevPreviewSession(devState)

  return (
    <>
      <Console session={session} />

      {/* TEMPORARY dev-only state switcher — deleted once Block 3 wires
          the real session state from the API. Lets us check the shell
          reacts correctly to every `estado` without a live backend. */}
      <div className="dev-state-switcher">
        <span className="dev-state-switcher__label">Dev preview de estado:</span>
        <button type="button" onClick={() => setDevState(null)}>
          (sin sesión)
        </button>
        {SESSION_STATES.map((state) => (
          <button key={state} type="button" onClick={() => setDevState(state)}>
            {state}
          </button>
        ))}
      </div>
    </>
  )
}

export default App
