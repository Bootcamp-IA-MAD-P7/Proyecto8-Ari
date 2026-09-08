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

// Screen copy and available actions per state (spec_front.md section 3
// table). Action labels are display copy only for now — Block 3 wires
// them to the API client and real form logic.
export const STATE_UI = {
  abierta: {
    stepLabel: 'Abierta',
    heading: 'Ficha recién abierta',
    description: 'Cargá los seis datos clínicos para la clasificación tabular.',
    actions: ['Clasificar riesgo tabular'],
  },
  clasificada_tabular: {
    stepLabel: 'Clasificada (tabular)',
    heading: 'Resultado tabular',
    description:
      'Elegí un camino: derivar a imagen, dar de alta, o derivar a especialista.',
    actions: ['Derivar a imagen', 'Alta', 'Derivar a especialista'],
  },
  derivada_imagen: {
    stepLabel: 'Derivada a imagen',
    heading: 'Pendiente de tomografía',
    description: 'Subí la TAC para la clasificación por imagen.',
    actions: ['Subir imagen'],
  },
  clasificada_imagen: {
    stepLabel: 'Clasificada (imagen)',
    heading: 'Resultado tabular e imagen',
    description: 'Elegí un camino de cierre: alta o derivar a especialista.',
    actions: ['Alta', 'Derivar a especialista'],
  },
  cerrada: {
    stepLabel: 'Cerrada',
    heading: 'Sesión cerrada',
    description: 'Rastro completo de la sesión, solo lectura.',
    actions: [],
  },
}
