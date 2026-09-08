// Session state machine (spec_front.md section 3, backed by
// reconocimiento_backend.md section 4 / app/models_db.py ESTADOS_VALIDOS).
// This is the single source of truth for state -> UI mapping ("la ley del
// render condicional"). Order matters: it drives the stepper's sequence.

export const SESSION_STATES = [
  'abierta',
  'clasificada_tabular',
  'derivada_imagen',
  'clasificada_imagen',
  'cerrada',
]

// Screen copy per state (spec_front.md section 3 table). The actions
// themselves are real components now (Block 3), wired in SessionPanel.jsx
// per `estado` — this module only owns the stepper label and the
// heading/description copy shown above whichever form/action is active.
export const STATE_UI = {
  abierta: {
    stepLabel: 'Abierta',
    heading: 'Datos clínicos del paciente',
    description: 'Cargá los seis datos clínicos para calcular el riesgo.',
  },
  clasificada_tabular: {
    stepLabel: 'Clasificada (tabular)',
    heading: 'Resultado tabular',
    description:
      'Elegí un camino: derivar a imagen, dar de alta, o derivar a especialista.',
  },
  derivada_imagen: {
    stepLabel: 'Derivada a imagen',
    heading: 'Pendiente de tomografía',
    description: 'Subí la TAC para la clasificación por imagen.',
  },
  clasificada_imagen: {
    stepLabel: 'Clasificada (imagen)',
    heading: 'Resultado tabular e imagen',
    description: 'Elegí un camino de cierre: alta o derivar a especialista.',
  },
  cerrada: {
    stepLabel: 'Cerrada',
    heading: 'Sesión cerrada',
    description: 'Rastro completo de la sesión, solo lectura.',
  },
}
