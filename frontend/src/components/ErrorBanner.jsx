import './ErrorBanner.css'

// Shows an ApiError's message (client.js already normalized status/kind
// into one safe-to-display string). Field-level detail from
// error.fieldErrors is rendered separately, next to each input.
function ErrorBanner({ error }) {
  if (!error) return null

  return (
    <div className="error-banner" role="alert">
      {error.message}
    </div>
  )
}

export default ErrorBanner
