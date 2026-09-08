// Thin fetch wrapper over the stroke-risk API. Pure data layer: no app
// state, no id_sesion tracking, no POST-then-GET orchestration — that is
// UI logic and belongs to later blocks (specs/spec_front.md Block 2+).
//
// Field names in request bodies match the backend contract exactly
// (specs/reconocimiento_backend.md): id_paciente, motivo_derivacion,
// decision_final, and the multipart field name "file".

import { API_BASE_URL } from '../config/api.js'

// Normalized error shape thrown by every function in this module on
// failure. The backend uses two different shapes for error bodies (see
// reconocimiento_backend.md section 9) and a 5xx isn't even JSON — this
// class collapses all of that into one predictable shape so the rest of
// the app never has to guess which one it got:
//
//   status       number | null   HTTP status, or null when fetch itself
//                                 failed (offline, CORS, DNS, ...).
//   kind         'validation' | 'http' | 'server' | 'network'
//   message      string          Always safe to display as-is.
//   fieldErrors  { [field]: string } | null
//                                 Only set when kind === 'validation'.
//
// kind meanings:
//   'validation' — 422 from Pydantic. Real `detail` is an array of
//     { loc, msg, type, input, ctx? } objects. fieldErrors maps the last
//     segment of each error's `loc` (the field name) to its `msg`, for
//     direct field-level display next to a form input.
//   'http'       — 404, 409, 413, or the image-upload 422s. Real `detail`
//     is a plain string; it becomes `message` unchanged.
//   'server'     — 5xx. The body is plain text ("Internal Server Error"),
//     never JSON — it is never parsed, `message` is a fixed generic string.
//   'network'    — fetch() itself threw before any response arrived.
export class ApiError extends Error {
  constructor({ status, kind, message, fieldErrors = null }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.kind = kind
    this.fieldErrors = fieldErrors
  }
}

// Builds the field -> message map for a Pydantic validation error array.
function toFieldErrors(detail) {
  const fieldErrors = {}
  for (const error of detail) {
    const loc = Array.isArray(error.loc) ? error.loc : []
    const field = loc.length > 0 ? loc[loc.length - 1] : 'unknown'
    fieldErrors[field] = error.msg
  }
  return fieldErrors
}

// Reads an error response body and normalizes it into an ApiError.
// Never calls response.json() on a 5xx: that body is plain text.
async function toApiError(response) {
  const status = response.status

  if (status >= 500) {
    return new ApiError({
      status,
      kind: 'server',
      message: 'The server had an unexpected problem. Please try again.',
    })
  }

  let body
  try {
    body = await response.json()
  } catch {
    return new ApiError({
      status,
      kind: 'http',
      message: `Request failed with status ${status}.`,
    })
  }

  const detail = body?.detail

  if (Array.isArray(detail)) {
    return new ApiError({
      status,
      kind: 'validation',
      message: detail.map((error) => error.msg).join(' '),
      fieldErrors: toFieldErrors(detail),
    })
  }

  return new ApiError({
    status,
    kind: 'http',
    message: typeof detail === 'string' ? detail : `Request failed with status ${status}.`,
  })
}

// Shared request path: resolve the URL, run fetch, and normalize both
// network failures and non-2xx responses into an ApiError. On success,
// returns the parsed JSON body as-is (no wrapping).
async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch {
    throw new ApiError({
      status: null,
      kind: 'network',
      message: 'Could not reach the server. Check your connection.',
    })
  }

  if (!response.ok) {
    throw await toApiError(response)
  }

  return response.json()
}

function requestJson(path, method, body) {
  return request(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// POST /sesiones -> { id_sesion, estado }
export function openSession(idPaciente) {
  return requestJson('/sesiones', 'POST', { id_paciente: idPaciente })
}

// POST /sesiones/{id}/clasificacion-tabular -> { probability, prediction, threshold, estado }
export function classifyTabular(idSesion, features) {
  return requestJson(`/sesiones/${idSesion}/clasificacion-tabular`, 'POST', features)
}

// POST /sesiones/{id}/derivacion -> { estado }
export function refer(idSesion, motivo) {
  return requestJson(`/sesiones/${idSesion}/derivacion`, 'POST', {
    motivo_derivacion: motivo,
  })
}

// POST /sesiones/{id}/clasificacion-imagen (multipart, field "file")
// -> { probability, prediction, threshold, estado }
export function classifyImage(idSesion, file) {
  const formData = new FormData()
  formData.append('file', file)
  // No Content-Type header here: the browser sets multipart/form-data
  // with the correct boundary on its own when the body is a FormData.
  return request(`/sesiones/${idSesion}/clasificacion-imagen`, {
    method: 'POST',
    body: formData,
  })
}

// POST /sesiones/{id}/cierre -> { estado }
export function closeSession(idSesion, decisionFinal) {
  return requestJson(`/sesiones/${idSesion}/cierre`, 'POST', {
    decision_final: decisionFinal,
  })
}

// GET /sesiones/{id} -> SesionOut (10 fields, see reconocimiento_backend.md section 3)
export function getSession(idSesion) {
  return request(`/sesiones/${idSesion}`)
}
