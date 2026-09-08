import { useState } from 'react'
import './forms.css'

// Six fields, exact contract (reconocimiento_backend.md section 5). The
// `value`s sent to the API are the literal enum strings/0-1 ints; only
// the on-screen labels are Spanish prose. min/max on the number inputs
// are UX guardrails, not a replacement for server validation.
const SMOKING_OPTIONS = [
  { value: 'never smoked', label: 'Nunca fumó' },
  { value: 'smokes', label: 'Fuma' },
  { value: 'formerly smoked', label: 'Fumaba antes' },
  { value: 'Unknown', label: 'Desconocido' },
]

const INITIAL_VALUES = {
  age: '',
  hypertension: 0,
  heart_disease: 0,
  avg_glucose_level: '',
  bmi: '',
  smoking_status: SMOKING_OPTIONS[0].value,
}

function TabularForm({ onSubmit, loading, fieldErrors }) {
  const [values, setValues] = useState(INITIAL_VALUES)

  function update(field, value) {
    setValues((prev) => ({ ...prev, [field]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    onSubmit({
      age: Number(values.age),
      hypertension: values.hypertension,
      heart_disease: values.heart_disease,
      avg_glucose_level: Number(values.avg_glucose_level),
      bmi: Number(values.bmi),
      smoking_status: values.smoking_status,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="form">
      <label htmlFor="age">Edad</label>
      <input
        id="age"
        type="number"
        min="0"
        max="110"
        step="any"
        required
        value={values.age}
        onChange={(event) => update('age', event.target.value)}
        disabled={loading}
      />
      {fieldErrors?.age && <p className="field-error">{fieldErrors.age}</p>}

      <fieldset>
        <legend>Hipertensión</legend>
        <label>
          <input
            type="radio"
            name="hypertension"
            checked={values.hypertension === 1}
            onChange={() => update('hypertension', 1)}
            disabled={loading}
          />
          Sí
        </label>
        <label>
          <input
            type="radio"
            name="hypertension"
            checked={values.hypertension === 0}
            onChange={() => update('hypertension', 0)}
            disabled={loading}
          />
          No
        </label>
      </fieldset>
      {fieldErrors?.hypertension && <p className="field-error">{fieldErrors.hypertension}</p>}

      <fieldset>
        <legend>Cardiopatía</legend>
        <label>
          <input
            type="radio"
            name="heart_disease"
            checked={values.heart_disease === 1}
            onChange={() => update('heart_disease', 1)}
            disabled={loading}
          />
          Sí
        </label>
        <label>
          <input
            type="radio"
            name="heart_disease"
            checked={values.heart_disease === 0}
            onChange={() => update('heart_disease', 0)}
            disabled={loading}
          />
          No
        </label>
      </fieldset>
      {fieldErrors?.heart_disease && <p className="field-error">{fieldErrors.heart_disease}</p>}

      <label htmlFor="avg_glucose_level">Glucosa promedio (mg/dl)</label>
      <input
        id="avg_glucose_level"
        type="number"
        min="40"
        max="400"
        step="any"
        required
        value={values.avg_glucose_level}
        onChange={(event) => update('avg_glucose_level', event.target.value)}
        disabled={loading}
      />
      {fieldErrors?.avg_glucose_level && (
        <p className="field-error">{fieldErrors.avg_glucose_level}</p>
      )}

      <label htmlFor="bmi">IMC</label>
      <input
        id="bmi"
        type="number"
        min="10"
        max="100"
        step="any"
        required
        value={values.bmi}
        onChange={(event) => update('bmi', event.target.value)}
        disabled={loading}
      />
      {fieldErrors?.bmi && <p className="field-error">{fieldErrors.bmi}</p>}

      <label htmlFor="smoking_status">Tabaquismo</label>
      <select
        id="smoking_status"
        value={values.smoking_status}
        onChange={(event) => update('smoking_status', event.target.value)}
        disabled={loading}
      >
        {SMOKING_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {fieldErrors?.smoking_status && <p className="field-error">{fieldErrors.smoking_status}</p>}

      <button type="submit" disabled={loading}>
        Clasificar riesgo tabular
      </button>
    </form>
  )
}

export default TabularForm
