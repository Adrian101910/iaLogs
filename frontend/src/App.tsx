import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { errorMessage, request } from './api'
import type { Analysis, LogEvent, Page } from './types'

const PAGE_SIZE = 25
const MAX_SELECTION = 50
const emptyFilters = { source: '', service: '', severity: '', start: '', end: '', text: '' }
type Filters = typeof emptyFilters
type View = 'events' | 'history' | 'analysis'

function Icon({ name, size = 20 }: { name: 'events' | 'history' | 'spark' | 'search' | 'arrow' | 'lock' | 'close' | 'refresh' | 'box'; size?: number }) {
  const paths = {
    events: <><path d="M8 6h12M8 12h12M8 18h12" /><path d="M3 6h.01M3 12h.01M3 18h.01" /></>,
    history: <><path d="M3 11a9 9 0 1 1 2.6 7" /><path d="M3 4v7h7M12 7v5l3 2" /></>,
    spark: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 3v4M18 5h4" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6" /></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" /></>,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    refresh: <><path d="M20 7a8 8 0 0 0-14-2L3 8m0-5v5h5M4 17a8 8 0 0 0 14 2l3-3m0 5v-5h-5" /></>,
    box: <><path d="m3 7 9-4 9 4v10l-9 4-9-4V7Zm0 0 9 4 9-4M12 11v10" /></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

function Logo() {
  return <div className="logo"><span className="logo-symbol" aria-hidden="true">i<span>↗</span></span><span>ia<span className="logo-light">Logs</span><small>OBSERVABILIDAD LOCAL</small></span></div>
}

function ErrorNotice({ children }: { children: ReactNode }) {
  return <div className="notice error" role="alert"><span aria-hidden="true">!</span><div>{children}</div></div>
}

function Loading({ children = 'Cargando…' }: { children?: ReactNode }) {
  return <div className="loading" role="status"><span className="spinner" />{children}</div>
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty"><span className="empty-icon"><Icon name="box" size={28} /></span><h3>{title}</h3><p>{children}</p></div>
}

function formatDate(date: string) {
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(date))
}

function SeverityBadge({ value }: { value: string }) {
  return <span className={`severity severity-${value.toLowerCase()}`}><span />{value}</span>
}

function Login({ onConnect }: { onConnect: (key: string) => void }) {
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef<AbortController | null>(null)
  useEffect(() => () => pending.current?.abort(), [])

  async function connect(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    const controller = new AbortController()
    pending.current?.abort()
    pending.current = controller
    try {
      await request<Page<LogEvent>>(key.trim(), '/v1/logs?limit=1', controller.signal)
      if (!controller.signal.aborted) onConnect(key.trim())
    } catch (cause) {
      if (!controller.signal.aborted) setError(errorMessage(cause))
    } finally {
      if (!controller.signal.aborted) setBusy(false)
    }
  }

  return <div className="login-page">
    <section className="login-story">
      <Logo />
      <div className="login-story-body"><span className="eyebrow">TUS SISTEMAS. TU CONTEXTO.</span><h1>De los eventos<br />a las evidencias.</h1><p>Reúne tus logs, encuentra lo relevante y explora posibles causas con inteligencia artificial local.</p>
        <div className="signal-art" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /><span /><span /></div>
        <div className="story-foot"><span className="status-dot" />Datos en tu equipo · IA con Ollama</div>
      </div>
      <p className="login-version">iaLogs / primera versión local</p>
    </section>
    <main className="login-main"><form className="login-card" onSubmit={connect}>
      <span className="login-lock"><Icon name="lock" size={24} /></span><span className="eyebrow">ESPACIO DE TRABAJO</span>
      <h2>Conecta con tus logs</h2><p>Introduce la API key que has configurado en el servidor para abrir el explorador.</p>
      <label htmlFor="api-key">API key</label><input id="api-key" type="password" autoComplete="off" autoCapitalize="off" spellCheck={false} value={key} onChange={event => setKey(event.target.value)} placeholder="Introduce tu clave de acceso" required disabled={busy} />
      {error && <ErrorNotice>{error}</ErrorNotice>}
      <button className="button primary login-submit" type="submit" disabled={busy || !key.trim()}>{busy ? <><span className="spinner" />Conectando…</> : <>Abrir explorador<Icon name="arrow" size={18} /></>}</button>
      <div className="memory-note"><Icon name="lock" size={16} /><span>La clave permanece solo en memoria. Al recargar o desconectar tendrás que introducirla de nuevo.</span></div>
    </form><p className="login-caption">Un punto de partida para entender lo que ocurre.</p></main>
  </div>
}

function Pager({ total, offset, onPage, busy }: { total: number; offset: number; onPage: (offset: number) => void; busy: boolean }) {
  return <div className="pager"><span>{total ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} de ${total.toLocaleString('es-ES')}` : '0 resultados'}</span><div><button className="button subtle" disabled={busy || offset === 0} onClick={() => onPage(Math.max(0, offset - PAGE_SIZE))}>← Anterior</button><span className="page-number">{Math.floor(offset / PAGE_SIZE) + 1}</span><button className="button subtle" disabled={busy || offset + PAGE_SIZE >= total} onClick={() => onPage(offset + PAGE_SIZE)}>Siguiente →</button></div></div>
}

function EventDetail({ event, loading, error, onClose }: { event: LogEvent | null; loading: boolean; error: string; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null)
  const dialog = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    close.current?.focus()
    function keyboard(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && dialog.current) {
        const focusable = Array.from(dialog.current.querySelectorAll<HTMLElement>('button, a[href], input, [tabindex="0"]'))
        const first = focusable[0], last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', keyboard)
    return () => { document.removeEventListener('keydown', keyboard); previous?.focus() }
  }, [onClose])
  return <div className="modal-backdrop" onClick={e => { if (e.target === e.currentTarget) onClose() }}><div className="detail-modal" ref={dialog} role="dialog" aria-modal="true" aria-labelledby="detail-title">
    <div className="modal-head"><div><span className="eyebrow">EVENTO ORIGINAL</span><h2 id="detail-title">Detalle del evento</h2></div><button className="icon-button" ref={close} onClick={onClose} aria-label="Cerrar detalle"><Icon name="close" /></button></div>
    {loading && <Loading>Buscando la evidencia…</Loading>}{error && <ErrorNotice>{error}</ErrorNotice>}
    {event && <><div className="detail-meta"><SeverityBadge value={event.severity} /><code>{event.id}</code></div><dl className="detail-fields"><div><dt>Fecha del evento</dt><dd>{formatDate(event.timestamp)}</dd></div><div><dt>Recibido</dt><dd>{formatDate(event.received_at)}</dd></div><div><dt>Origen</dt><dd>{event.source}</dd></div><div><dt>Servicio</dt><dd>{event.service || 'Sin servicio'}</dd></div></dl><h3>Mensaje</h3><pre className="message-detail" tabIndex={0}>{event.message}</pre><h3>Atributos JSON</h3><pre className="json-detail" tabIndex={0}>{JSON.stringify(event.attributes, null, 2)}</pre></>}
  </div></div>
}

function AnalysisResult({ analysis, onEvidence }: { analysis: Analysis; onEvidence: (id: string) => void }) {
  const diagnosis = analysis.diagnosis
  const uncertainty = { low: 'Baja', medium: 'Media', high: 'Alta' }[diagnosis.uncertainty]
  function citations(ids: string[]) {
    return <div className="citations">{ids.map(id => <button className="evidence-link" key={id} onClick={() => onEvidence(id)} title={id}>↗ {id.slice(0, 8)}</button>)}</div>
  }
  return <div className="result-view"><div className="analysis-meta"><span><Icon name="spark" size={16} />{analysis.model}</span><span>{formatDate(analysis.created_at)}</span><span>{analysis.log_ids.length} eventos utilizados</span><span>Prompt {analysis.prompt_version}</span></div>
    <section className="summary-card"><span className="eyebrow">RESUMEN DEL DIAGNÓSTICO</span><p>{diagnosis.summary}</p><div className="summary-foot"><span className="uncertainty">Incertidumbre {uncertainty.toLowerCase()}</span><span>Las causas propuestas son hipótesis que requieren comprobación.</span></div></section>
    <div className="result-grid"><section className="panel result-card"><div className="section-heading"><span className="section-index">01</span><h2>Hallazgos</h2></div>{diagnosis.findings.length ? diagnosis.findings.map((finding, index) => <div className="finding" key={index}><p>{finding.description}</p>{citations(finding.log_ids)}</div>) : <p className="muted">Sin hallazgos concluyentes.</p>}</section>
      <section className="panel result-card"><div className="section-heading"><span className="section-index">02</span><h2>Causas posibles</h2></div>{diagnosis.possible_causes.length ? diagnosis.possible_causes.map((cause, index) => <div className="finding" key={index}><span className="hypothesis">HIPÓTESIS</span><p>{cause.description}</p>{citations(cause.log_ids)}</div>) : <p className="muted">No se han propuesto causas.</p>}</section>
      <section className="panel result-card evidence-card"><div className="section-heading"><span className="section-index">03</span><h2>Evidencias</h2></div>{diagnosis.evidence.map((evidence, index) => <div className="evidence-row" key={`${evidence.log_id}-${index}`}><button className="evidence-link" title={evidence.log_id} onClick={() => onEvidence(evidence.log_id)}>↗ {evidence.log_id.slice(0, 8)}</button><p>{evidence.explanation}</p></div>)}</section>
      <section className="panel result-card"><div className="section-heading"><span className="section-index">04</span><h2>Próximas comprobaciones</h2></div>{diagnosis.next_checks.length ? <ol className="check-list">{diagnosis.next_checks.map((check, i) => <li key={i}>{check}</li>)}</ol> : <p className="muted">Sin comprobaciones sugeridas.</p>}</section>
      <section className="panel result-card"><div className="section-heading"><span className="section-index">05</span><h2>Información que falta</h2></div>{diagnosis.missing_information.length ? <ul className="plain-list">{diagnosis.missing_information.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="muted">El modelo no ha indicado información adicional.</p>}<p className="uncertainty-note">Incertidumbre cualitativa: <strong>{uncertainty}</strong>. El diagnóstico está limitado a los eventos seleccionados.</p></section>
    </div><p className="result-id">Análisis {analysis.id}</p></div>
}

function Dashboard({ apiKey, onDisconnect }: { apiKey: string; onDisconnect: () => void }) {
  const [view, setView] = useState<View>('events')
  const [draft, setDraft] = useState<Filters>(emptyFilters)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [offset, setOffset] = useState(0)
  const [events, setEvents] = useState<Page<LogEvent>>({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 })
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [selectionError, setSelectionError] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [history, setHistory] = useState<Page<Analysis>>({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 })
  const [historyOffset, setHistoryOffset] = useState(0)
  const [historyBusy, setHistoryBusy] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [detailOpen, setDetailOpen] = useState(false)
  const [detail, setDetail] = useState<LogEvent | null>(null)
  const [detailBusy, setDetailBusy] = useState(false)
  const [detailError, setDetailError] = useState('')
  const pending = useRef(new Set<AbortController>())
  const detailRequest = useRef<AbortController | null>(null)
  const analysisRequest = useRef<AbortController | null>(null)
  const historyDetailRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    const requests = pending.current
    return () => { for (const controller of requests) controller.abort(); detailRequest.current?.abort(); analysisRequest.current?.abort(); historyDetailRequest.current?.abort() }
  }, [])

  useEffect(() => {
    if (view !== 'events') return
    const controller = new AbortController()
    pending.current.add(controller)
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) })
    Object.entries(filters).forEach(([name, value]) => {
      if (value) params.set(name, name === 'start' || name === 'end' ? new Date(value).toISOString() : value)
    })
    setBusy(true)
    setError('')
    request<Page<LogEvent>>(apiKey, `/v1/logs?${params}`, controller.signal)
      .then(data => { if (!controller.signal.aborted) setEvents(data) })
      .catch(cause => { if (!controller.signal.aborted) setError(errorMessage(cause)) })
      .finally(() => { pending.current.delete(controller); if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [apiKey, filters, offset, refresh, view])

  useEffect(() => {
    if (view !== 'history') return
    const controller = new AbortController()
    pending.current.add(controller)
    setHistoryBusy(true)
    setHistoryError('')
    request<Page<Analysis>>(apiKey, `/v1/analyses?limit=${PAGE_SIZE}&offset=${historyOffset}`, controller.signal)
      .then(data => { if (!controller.signal.aborted) setHistory(data) })
      .catch(cause => { if (!controller.signal.aborted) setHistoryError(errorMessage(cause)) })
      .finally(() => { pending.current.delete(controller); if (!controller.signal.aborted) setHistoryBusy(false) })
    return () => controller.abort()
  }, [apiKey, historyOffset, refresh, view])

  const closeDetail = useCallback(() => { detailRequest.current?.abort(); setDetailOpen(false); setDetail(null); setDetailError('') }, [])

  function navigate(nextView: View) {
    historyDetailRequest.current?.abort()
    setView(nextView)
  }

  async function showEvidence(id: string) {
    detailRequest.current?.abort()
    const controller = new AbortController()
    detailRequest.current = controller
    setDetail(null)
    setDetailError('')
    setDetailBusy(true)
    setDetailOpen(true)
    try {
      const event = await request<LogEvent>(apiKey, `/v1/logs/${encodeURIComponent(id)}`, controller.signal)
      if (!controller.signal.aborted) setDetail(event)
    } catch (cause) { if (!controller.signal.aborted) setDetailError(errorMessage(cause)) }
    finally { if (!controller.signal.aborted) setDetailBusy(false) }
  }

  function showEvent(event: LogEvent) {
    detailRequest.current?.abort()
    setDetail(event)
    setDetailBusy(false)
    setDetailError('')
    setDetailOpen(true)
  }

  function toggleSelection(id: string) {
    setSelectionError('')
    if (!selected.has(id) && selected.size >= MAX_SELECTION) {
      setSelectionError(`La selección está limitada a ${MAX_SELECTION} eventos.`)
      return
    }
    setSelected(previous => {
      const next = new Set(previous)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function togglePage() {
    setSelectionError('')
    const ids = events.items.map(event => event.id)
    const allSelected = ids.every(id => selected.has(id))
    const wouldExceedLimit = !allSelected && new Set([...selected, ...ids]).size > MAX_SELECTION
    if (wouldExceedLimit) setSelectionError(`La selección está limitada a ${MAX_SELECTION} eventos.`)
    setSelected(previous => {
      const next = new Set(previous)
      if (allSelected) ids.forEach(id => next.delete(id))
      else {
        for (const id of ids) {
          if (next.size >= MAX_SELECTION) break
          next.add(id)
        }
      }
      return next
    })
  }

  async function analyze() {
    if (!selected.size || analyzing) return
    analysisRequest.current?.abort()
    const controller = new AbortController()
    analysisRequest.current = controller
    setAnalyzing(true)
    setAnalysisError('')
    try {
      const result = await request<Analysis>(apiKey, '/v1/analyses', controller.signal, { log_ids: Array.from(selected) })
      if (!controller.signal.aborted) { setAnalysis(result); setView('analysis'); setRefresh(value => value + 1) }
    } catch (cause) { if (!controller.signal.aborted) setAnalysisError(errorMessage(cause)) }
    finally { if (!controller.signal.aborted) setAnalyzing(false) }
  }

  async function openAnalysis(id: string) {
    historyDetailRequest.current?.abort()
    const controller = new AbortController()
    historyDetailRequest.current = controller
    setHistoryBusy(true)
    setHistoryError('')
    try {
      const result = await request<Analysis>(apiKey, `/v1/analyses/${encodeURIComponent(id)}`, controller.signal)
      if (!controller.signal.aborted) { setAnalysis(result); setView('analysis') }
    } catch (cause) { if (!controller.signal.aborted) setHistoryError(errorMessage(cause)) }
    finally { if (!controller.signal.aborted) setHistoryBusy(false) }
  }

  function applyFilters(event: FormEvent) {
    event.preventDefault()
    if (draft.start && draft.end && new Date(draft.start) > new Date(draft.end)) { setError('La fecha inicial debe ser anterior a la fecha final.'); return }
    setOffset(0)
    setFilters({ ...draft })
  }

  const activeFilterCount = Object.values(filters).filter(Boolean).length
  const pageSelected = events.items.length > 0 && events.items.every(event => selected.has(event.id))
  const heading = view === 'events' ? 'Explorador de eventos' : view === 'history' ? 'Historial de análisis' : 'Diagnóstico con evidencias'
  return <div className="app-shell">
    <aside className="sidebar"><Logo /><div className="workspace-label">ESPACIO LOCAL</div><nav aria-label="Navegación principal"><button aria-label="Eventos" className={view === 'events' ? 'active' : ''} onClick={() => navigate('events')}><Icon name="events" />Eventos<span className="nav-arrow">↗</span></button><button aria-label="Historial de análisis" className={view === 'history' || view === 'analysis' ? 'active' : ''} onClick={() => navigate('history')}><Icon name="history" />Análisis</button></nav>
      <div className="sidebar-info"><span className="local-symbol"><Icon name="spark" /></span><h3>El contexto importa.</h3><p>Selecciona los eventos relevantes y deja que tu IA local conecte las evidencias.</p><span className="local-tag"><span className="status-dot" />OLLAMA · LOCAL</span></div>
      <div className="sidebar-bottom"><div><Icon name="lock" size={15} /><span>API key solo en memoria</span></div><button onClick={onDisconnect} aria-label="Desconectar">Desconectar <span aria-hidden="true">↗</span></button><small>iaLogs · v0.1</small></div></aside>
    <div className="workspace"><header className="topbar"><span className="breadcrumb">Espacio de trabajo <span>/</span> <strong>{view === 'events' ? 'Eventos' : 'Análisis'}</strong></span><span className="connection-tag"><span className="status-dot" />Sesión local</span></header>
      <main className="main-content"><div className="page-heading"><div><span className="eyebrow">OBSERVA. SELECCIONA. COMPRENDE.</span><h1>{heading}</h1><p>{view === 'events' ? 'Encuentra la señal entre todos los eventos de tus sistemas.' : view === 'history' ? 'Recupera los diagnósticos y las evidencias que los sustentan.' : 'Un análisis acotado a los eventos que has seleccionado.'}</p></div>{view === 'analysis' ? <button className="button secondary" onClick={() => setView('history')}>← Ver historial</button> : <button className="button secondary" disabled={busy && view === 'events' || historyBusy && view === 'history'} onClick={() => setRefresh(value => value + 1)}><Icon name="refresh" size={16} />Actualizar</button>}</div>
        {view === 'events' && <>
          <div className="overview-strip"><div><span className="overview-icon"><Icon name="events" /></span><span><strong>{busy ? '—' : events.total.toLocaleString('es-ES')}</strong><small>Eventos encontrados</small></span></div><div><span className="overview-icon violet"><Icon name="spark" /></span><span><strong>{selected.size.toString().padStart(2, '0')}</strong><small>En tu selección</small></span></div><div className="overview-hint"><span className="status-dot" /><p>La ingesta y la consulta funcionan<br />sin conexión con Ollama.</p></div></div>
          <section className="panel filters-panel" aria-labelledby="filter-title"><div className="panel-title"><h2 id="filter-title"><Icon name="search" size={17} />Filtrar eventos</h2>{activeFilterCount > 0 && <span className="filter-count">{activeFilterCount} activos</span>}</div><form onSubmit={applyFilters}><div className="filter-grid"><label className="search-field">Buscar en el mensaje<input value={draft.text} placeholder="Error, conexión, timeout…" maxLength={500} onChange={e => setDraft({ ...draft, text: e.target.value })} /></label><label>Origen<input value={draft.source} placeholder="Todos los orígenes" maxLength={255} onChange={e => setDraft({ ...draft, source: e.target.value })} /></label><label>Servicio<input value={draft.service} placeholder="Todos los servicios" maxLength={255} onChange={e => setDraft({ ...draft, service: e.target.value })} /></label><label>Severidad<select value={draft.severity} onChange={e => setDraft({ ...draft, severity: e.target.value })}><option value="">Todas las severidades</option>{['TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map(value => <option key={value}>{value}</option>)}</select></label><label>Desde · hora local<input type="datetime-local" value={draft.start} onChange={e => setDraft({ ...draft, start: e.target.value })} /></label><label>Hasta · hora local<input type="datetime-local" value={draft.end} onChange={e => setDraft({ ...draft, end: e.target.value })} /></label></div><div className="filter-actions"><button type="button" className="text-button" onClick={() => { setDraft(emptyFilters); setFilters(emptyFilters); setOffset(0); setError('') }}>Limpiar filtros</button><button className="button secondary small" type="submit">Aplicar filtros<Icon name="arrow" size={15} /></button></div></form></section>
          {error && <ErrorNotice>{error}</ErrorNotice>}{selectionError && <ErrorNotice>{selectionError}</ErrorNotice>}{analysisError && <ErrorNotice>{analysisError}</ErrorNotice>}
          <section className="panel events-panel" aria-labelledby="event-table-title"><div className="table-heading"><div><h2 id="event-table-title">Flujo de eventos</h2><span>Más recientes primero · fechas en tu hora local</span></div><span className="table-count">{events.limit} por página</span></div>
            {busy ? <Loading>Cargando eventos…</Loading> : error ? <Empty title="No se han podido cargar los eventos">Revisa el error y vuelve a actualizar.</Empty> : events.items.length === 0 ? <Empty title={activeFilterCount ? 'Sin coincidencias' : 'Todo empieza con un evento'}>{activeFilterCount ? 'Prueba con otros filtros o amplía el intervalo temporal.' : 'Envía un lote a la API o ejecuta el script de eventos sintéticos para empezar.'}</Empty> : <div className="table-scroll"><table><thead><tr><th className="checkbox-cell"><input type="checkbox" checked={pageSelected} onChange={togglePage} aria-label="Seleccionar los eventos de esta página" disabled={analyzing} /></th><th>FECHA / HORA</th><th>SEVERIDAD</th><th>ORIGEN / SERVICIO</th><th>MENSAJE</th><th><span className="sr-only">Detalle</span></th></tr></thead><tbody>{events.items.map(event => <tr key={event.id} className={selected.has(event.id) ? 'selected-row' : ''}><td className="checkbox-cell"><input type="checkbox" checked={selected.has(event.id)} onChange={() => toggleSelection(event.id)} disabled={analyzing} aria-label={`Seleccionar evento ${event.id}`} /></td><td className="date-cell"><span>{new Date(event.timestamp).toLocaleDateString('es-ES')}</span><small>{new Date(event.timestamp).toLocaleTimeString('es-ES', { hour12: false })}</small></td><td><SeverityBadge value={event.severity} /></td><td className="source-cell"><strong>{event.source}</strong><small>{event.service || 'Sin servicio'}</small></td><td className="message-cell"><button onClick={() => showEvent(event)} title={event.message}>{event.message}</button></td><td><button className="icon-button row-detail" onClick={() => showEvent(event)} aria-label={`Ver detalle del evento ${event.id}`}><Icon name="arrow" size={17} /></button></td></tr>)}</tbody></table></div>}
            <Pager total={events.total} offset={offset} onPage={setOffset} busy={busy} /></section>
          <div className={`selection-bar ${selected.size ? 'has-selection' : ''}`}><div><span className="selection-mark"><Icon name="spark" /></span><div><strong>{selected.size ? `${selected.size} evento${selected.size === 1 ? '' : 's'} seleccionado${selected.size === 1 ? '' : 's'}` : 'Conecta los puntos con IA local'}</strong><p>{analyzing ? 'El modelo está preparando el diagnóstico. Puede tardar unos minutos.' : `Selecciona hasta ${MAX_SELECTION} eventos, incluso de páginas distintas.`}</p></div></div><div className="selection-actions">{selected.size > 0 && <button className="text-button" disabled={analyzing} onClick={() => { setSelected(new Set()); setSelectionError('') }}>Vaciar selección</button>}<button className="button primary" disabled={!selected.size || analyzing} onClick={analyze}>{analyzing ? <><span className="spinner" />Analizando…</> : <><Icon name="spark" size={17} />Analizar selección</>}</button></div></div>
        </>}
        {view === 'history' && <>{historyError && <ErrorNotice>{historyError}</ErrorNotice>}<section className="panel history-panel"><div className="table-heading"><div><h2>Diagnósticos guardados</h2><span>El contexto y las evidencias de cada análisis</span></div><span className="table-count">{history.total} en total</span></div>{historyBusy ? <Loading>Cargando análisis…</Loading> : historyError ? <Empty title="No se ha podido cargar el historial">Vuelve a actualizar cuando la API esté disponible.</Empty> : history.items.length ? <div className="history-list">{history.items.map(item => <button className="history-item" key={item.id} onClick={() => openAnalysis(item.id)}><span className="history-icon"><Icon name="spark" /></span><span className="history-content"><strong>{item.diagnosis.summary}</strong><span>{formatDate(item.created_at)}<span>·</span>{item.log_ids.length} eventos<span>·</span>{item.model}</span></span><Icon name="arrow" size={18} /></button>)}</div> : <Empty title="Un historial por construir">Selecciona eventos en el explorador y solicita tu primer diagnóstico.</Empty>}<Pager total={history.total} offset={historyOffset} onPage={setHistoryOffset} busy={historyBusy} /></section></>}
        {view === 'analysis' && analysis && <AnalysisResult analysis={analysis} onEvidence={showEvidence} />}
        <footer className="workspace-footer"><span>iaLogs <span> / </span> Observabilidad bajo tu control</span><span>Los diagnósticos son recomendaciones para revisar.</span></footer>
      </main>
    </div>
    {detailOpen && <EventDetail event={detail} loading={detailBusy} error={detailError} onClose={closeDetail} />}
  </div>
}

export default function App() {
  const [apiKey, setApiKey] = useState<string | null>(null)
  return apiKey === null ? <Login onConnect={setApiKey} /> : <Dashboard apiKey={apiKey} onDisconnect={() => setApiKey(null)} />
}
