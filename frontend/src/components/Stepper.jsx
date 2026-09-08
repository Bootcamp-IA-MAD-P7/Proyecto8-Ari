import { SESSION_STATES, STATE_UI } from '../domain/sessionStates.js'
import './Stepper.css'

// Read-only cycle stepper (spec_front.md section 3: "Stepper de ciclo que
// refleja, en solo lectura, en qué punto va la sesión"). Highlights only
// the current state — it does not mark earlier nodes as "done", because
// the direct-discharge path (clasificada_tabular -> cerrada) skips
// derivada_imagen and clasificada_imagen entirely, and a fake checkmark on
// steps a session never went through would misrepresent its history.
//
// currentState is null when there is no active session yet: every node
// renders neutral in that case.
function Stepper({ currentState }) {
  return (
    <ol className="stepper">
      {SESSION_STATES.map((state) => {
        const isCurrent = state === currentState
        const isClosed = state === 'cerrada'
        return (
          <li
            key={state}
            className={
              'stepper__step' +
              (isCurrent ? ' stepper__step--current' : '') +
              (isCurrent && isClosed ? ' stepper__step--done' : '')
            }
          >
            <span className="stepper__dot" aria-hidden="true" />
            <span className="stepper__label">{STATE_UI[state].stepLabel}</span>
          </li>
        )
      })}
    </ol>
  )
}

export default Stepper
