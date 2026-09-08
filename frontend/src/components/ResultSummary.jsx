import './ResultSummary.css'

// Renders a { probability, prediction, threshold } result (spec_front.md
// section 5). The verdict label AND its color are built from `prediction`
// — never a text/color field the backend doesn't send. Color is a
// contained badge (a left accent bar), never the card background: the
// screen must not visually lean on the clinical decision (section 7).
// Contrast of --color-risk-red against white/cream verified AA (see
// Block 4 checkpoint notes) before this landed.
function ResultSummary({ title, result }) {
  if (!result) return null

  const isHighRisk = result.prediction === 1
  const riskLabel = isHighRisk ? 'Riesgo alto' : 'Riesgo bajo'
  const badgeClass = 'risk-badge ' + (isHighRisk ? 'risk-badge--high' : 'risk-badge--low')

  const probabilityPct = Math.round(result.probability * 100)
  const thresholdPct = Math.round(result.threshold * 100)

  return (
    <div className="result-summary">
      <h3>{title}</h3>
      <span className={badgeClass}>{riskLabel}</span>
      <p className="result-summary__detail">
        Probabilidad estimada {probabilityPct}% · Umbral de decisión {thresholdPct}%
      </p>
      <p className="result-summary__disclaimer">
        Orientación de criba previa a la consulta. No es un diagnóstico.
      </p>
    </div>
  )
}

export default ResultSummary
