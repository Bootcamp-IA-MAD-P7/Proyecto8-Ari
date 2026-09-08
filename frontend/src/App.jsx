import { useState } from 'react'
import Console from './components/Console.jsx'
import {
  openSession,
  classifyTabular,
  refer,
  classifyImage,
  closeSession,
  getSession,
  ApiError,
} from './api/client.js'

// App-level session state. A single active session (spec_front.md
// section 1 scope), held in memory only — never localStorage/
// sessionStorage, never logged (section 6: no PHI in the browser beyond
// the running app's own memory).
function App() {
  const [session, setSession] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const sessionId = session?.id_sesion ?? null

  async function refreshSession(id) {
    const fresh = await getSession(id)
    setSession(fresh)
  }

  // Regla de oro (spec_front.md section 3): la UI solo muestra las
  // acciones que el estado permite, asi que un 409 casi no deberia
  // pasar. Si igual llega, mostramos el mensaje Y resincronizamos con
  // el server via GET -- nunca confiamos en la copia local.
  async function handleFailure(err, idForResync) {
    if (!(err instanceof ApiError)) throw err
    setError(err)
    if (err.status === 409 && idForResync) {
      try {
        await refreshSession(idForResync)
      } catch {
        // Resync itself failed; keep showing the original error.
      }
    }
  }

  // Shared POST-then-GET runner (spec_front.md section 4): every action
  // clears the previous error, runs, and on success the GET inside
  // `action` has already repainted `session` from the server's truth.
  async function withRequest(action, idForResync) {
    setLoading(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      await handleFailure(err, idForResync)
    } finally {
      setLoading(false)
    }
  }

  function handleOpenSession(idPaciente) {
    return withRequest(async () => {
      const opened = await openSession(idPaciente)
      await refreshSession(opened.id_sesion)
    }, null)
  }

  function handleClassifyTabular(features) {
    return withRequest(async () => {
      await classifyTabular(sessionId, features)
      await refreshSession(sessionId)
    }, sessionId)
  }

  function handleRefer(motivo) {
    return withRequest(async () => {
      await refer(sessionId, motivo)
      await refreshSession(sessionId)
    }, sessionId)
  }

  function handleClassifyImage(file) {
    return withRequest(async () => {
      await classifyImage(sessionId, file)
      await refreshSession(sessionId)
    }, sessionId)
  }

  function handleCloseSession(decisionFinal) {
    return withRequest(async () => {
      await closeSession(sessionId, decisionFinal)
      await refreshSession(sessionId)
    }, sessionId)
  }

  return (
    <Console
      session={session}
      error={error}
      loading={loading}
      onOpenSession={handleOpenSession}
      onClassifyTabular={handleClassifyTabular}
      onRefer={handleRefer}
      onClassifyImage={handleClassifyImage}
      onCloseSession={handleCloseSession}
    />
  )
}

export default App
