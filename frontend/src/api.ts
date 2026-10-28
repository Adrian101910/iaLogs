export async function request<T>(key: string, path: string, signal: AbortSignal, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'X-API-Key': key, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      credentials: 'omit',
      cache: 'no-store',
    })
  } catch (error) {
    if (signal.aborted) throw error
    throw new Error('No se puede conectar con iaLogs. Comprueba que la API está en marcha.')
  }
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) throw new Error('La API key no es válida. Revisa la clave configurada en el servidor.')
    let message = `La solicitud no se pudo completar (HTTP ${response.status}).`
    try {
      const data: { detail?: unknown } = await response.json()
      if (typeof data.detail === 'string') message = data.detail
      else if (Array.isArray(data.detail)) message = 'Los datos enviados no son válidos. Revisa los filtros o la selección.'
    } catch { /* Keep the safe fallback when a proxy returns a non-JSON error. */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Ha ocurrido un error inesperado.'
}
