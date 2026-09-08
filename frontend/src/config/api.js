// Single source of truth for the backend base URL. Read from Vite's env
// (VITE_API_BASE_URL) with a fallback matching uvicorn's default port.
// See specs/spec_front.md section 2: the 8000 fallback is an inference,
// not a guarantee — confirm it matches the running API.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
