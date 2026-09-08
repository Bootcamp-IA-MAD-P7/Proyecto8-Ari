import './ResultSummary.css'

// Renders a { probability, prediction, threshold } result (spec_front.md
// section 5). The label is built from `prediction`, never from a text
// field the backend doesn't send. No risk-red styling yet: the color
// treatment for high risk is Block 4 (section 7).
function ResultSummary({ title, result }) {
  if (!result) return null

  const riskLabel = result.prediction === 1 ? 'Riesgo alto' : 'Riesgo bajo'

  return (
    <div className="result-summary">
      <h3>{title}</h3>
      <p className="result-summary__risk">{riskLabel}</p>
      <p className="result-summary__detail">
        probabilidad {result.probability.toFixed(2)} · umbral {result.threshold}
      </p>
    </div>
  )
}

export default ResultSummary
