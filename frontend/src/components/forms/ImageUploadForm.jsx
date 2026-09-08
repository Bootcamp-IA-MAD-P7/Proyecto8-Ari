import { useState } from 'react'
import './forms.css'

// Client-side pre-check as UX only (spec_front.md section 5): the server
// still runs its own four filters (reconocimiento_backend.md section 7)
// and is the judge. Multipart field name is "file", exact.
const ACCEPTED_TYPES = ['image/png', 'image/jpeg']
const MAX_BYTES = 10 * 1024 * 1024

function ImageUploadForm({ onSubmit, loading, fieldErrors }) {
  const [file, setFile] = useState(null)
  const [precheckError, setPrecheckError] = useState(null)

  function handleFileChange(event) {
    const selected = event.target.files?.[0] ?? null
    setFile(selected)

    if (!selected) {
      setPrecheckError(null)
    } else if (!ACCEPTED_TYPES.includes(selected.type)) {
      setPrecheckError('Solo se aceptan archivos PNG o JPEG.')
    } else if (selected.size > MAX_BYTES) {
      setPrecheckError('El archivo supera los 10 MB.')
    } else {
      setPrecheckError(null)
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (!file || precheckError) return
    onSubmit(file)
  }

  return (
    <form onSubmit={handleSubmit} className="form">
      <label htmlFor="file">Tomografía (PNG o JPEG, hasta 10 MB)</label>
      <input
        id="file"
        type="file"
        accept="image/png,image/jpeg"
        onChange={handleFileChange}
        disabled={loading}
      />
      {precheckError && <p className="field-error">{precheckError}</p>}
      {fieldErrors?.file && <p className="field-error">{fieldErrors.file}</p>}

      <button type="submit" disabled={loading || !file || Boolean(precheckError)}>
        Subir imagen
      </button>
    </form>
  )
}

export default ImageUploadForm
