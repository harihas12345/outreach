import React, { useCallback, useEffect, useMemo, useState } from 'react'

type Notification = {
  id: string
  studentId: string
  studentName: string
  slackUserId: string
  message: string
  createdAtIso: string
  status: string
}

const PRESIGN_URL = String((import.meta as any).env?.VITE_PRESIGN_URL || '')
const BACKEND_URL = String((import.meta as any).env?.VITE_BACKEND_URL || '')
const S3_PREFIX = String((import.meta as any).env?.VITE_S3_PREFIX || 'uploads')
const SLACK_TEAM_ID = String((import.meta as any).env?.VITE_SLACK_TEAM_ID || 'T0HQD7V5M')
const HAS_PRESIGN = !!PRESIGN_URL

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [filter, setFilter] = useState('pending')
  const [toast, setToast] = useState<string>("")
  const [messageAll, setMessageAll] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const url = `${BACKEND_URL.replace(/\/$/, '')}/notifications${filter ? `?status=${filter}` : ''}`
      const resp = await fetch(url)
      if (!resp.ok) throw new Error('backend not reachable')
      const data = await resp.json()
      setNotifications(Array.isArray(data) ? data : [])
    } catch {
      setNotifications([])
    }
  }, [filter])

  useEffect(() => { void refresh() }, [refresh])

  const onUpload = useCallback(async () => {
    if (!file) return
    setUploading(true)
    try {
      if (PRESIGN_URL) {
        // S3 upload path
        const presignResp = await fetch(PRESIGN_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fileName: file.name, prefix: S3_PREFIX }),
        })
        if (!presignResp.ok) {
          throw new Error(`Presign failed (${presignResp.status})`)
        }
        const raw = await presignResp.json()
        const presigned = raw?.presigned ?? raw
        if (!presigned?.url || !presigned?.fields) {
          throw new Error('Invalid presign response')
        }
        const formData = new FormData()
        Object.entries(presigned.fields as Record<string, string>).forEach(([k, v]) => formData.append(k, String(v)))
        formData.append('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        formData.append('file', file)
        const s3Post = await fetch(presigned.url, { method: 'POST', body: formData })
        if (!s3Post.ok) throw new Error('S3 upload failed')
        setFile(null)
        setToast('File uploaded to S3. Processing…')
        setTimeout(() => void refresh(), 3000)
      } else {
        // Direct backend upload path
        if (!BACKEND_URL) throw new Error('Set VITE_BACKEND_URL')
        const formData = new FormData()
        formData.append('file', file)
        formData.append('messageAll', String(messageAll))
        const resp = await fetch(`${BACKEND_URL.replace(/\/$/, '')}/ingest-upload`, { method: 'POST', body: formData })
        if (!resp.ok) throw new Error('Upload ingest failed')
        setFile(null)
        setToast('File analyzed. Refreshing…')
        setTimeout(() => void refresh(), 1500)
      }
    } catch (e) {
      console.error(e)
      setToast('Upload failed')
    } finally {
      setUploading(false)
    }
  }, [file, refresh, messageAll])

  const onRunAnalysis = useCallback(async () => {
    if (!BACKEND_URL) {
      setToast('Set VITE_BACKEND_URL in the frontend environment')
      return
    }
    setUploading(true)
    try {
      const resp = await fetch(`${BACKEND_URL.replace(/\/$/, '')}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messageAll }),
      })
      if (!resp.ok) throw new Error('Ingest failed')
      setToast('Analysis queued. Refreshing…')
      setTimeout(() => void refresh(), 1500)
    } catch (e) {
      console.error(e)
      setToast('Ingest failed')
    } finally {
      setUploading(false)
    }
  }, [refresh, messageAll])

  const onApprove = useCallback(async (n: Notification) => {
    try {
      const resp = await fetch(`${BACKEND_URL.replace(/\/$/, '')}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notificationId: n.id, decision: 'approve' }),
      })
      let data: any = {}
      try { data = await resp.json() } catch {}
      if (resp.ok && data?.action === 'open_slack') {
        // Copy the drafted message to clipboard for quick paste
        if (data?.message && navigator?.clipboard?.writeText) {
          try { await navigator.clipboard.writeText(String(data.message)) } catch {}
        }
        // Stash payload for optional browser extension on Slack Web
        try {
          sessionStorage.setItem('aci_msg', String(data?.message || ''))
          sessionStorage.setItem('aci_user', String(n.slackUserId || ''))
        } catch {}
        // Also open Slack Web with payload for the helper extension
        try {
          const webUrl = String(data?.webDmUrl || `https://app.slack.com/client/${SLACK_TEAM_ID}/user_profile/${encodeURIComponent(n.slackUserId)}`) + `?aci_msg=${encodeURIComponent(String(data?.message || ''))}&aci_user=${encodeURIComponent(n.slackUserId)}`
          window.open(webUrl, '_blank', 'noopener')
        } catch {}
        // Additionally open the native slack:// deep link if available (desktop app opens DM reliably)
        try {
          if (data?.deepLink) {
            window.open(String(data.deepLink), '_blank', 'noopener')
          }
        } catch {}
        // Inform the user
        if (data?.message) alert('Message copied. If a Slack helper extension is installed, it will paste/send automatically. Otherwise, paste (Ctrl+V) and send.')
      }
    } catch (e) {
      console.error(e)
    } finally {
      void refresh()
    }
  }, [refresh])

  const onDeny = useCallback(async (id: string) => {
    await fetch(`${BACKEND_URL.replace(/\/$/, '')}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notificationId: id, decision: 'deny' }),
    })
    void refresh()
  }, [refresh])

  const onSaveMessage = useCallback(async (id: string, message: string) => {
    await fetch(`${BACKEND_URL.replace(/\/$/, '')}/edit-message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notificationId: id, message }),
    })
    void refresh()
  }, [refresh])

  return (
    <div className="container">
      <div className="app-header">
        <div>
          <div className="title">ACI Progress</div>
          <div className="subtitle">Upload sheets, curate messages, approve or deny</div>
        </div>
      </div>
      {toast && <div className="toast">{toast}</div>}

      <div className="grid">
        <section className="card">
          <h2>{HAS_PRESIGN ? 'Upload weekly Excel' : 'Run analysis (no upload configured)'}</h2>
          <div className="row" style={{ marginTop: 8 }}>
            {HAS_PRESIGN ? (
              <>
                <input className="input" type="file" accept=".xlsx" onChange={e => setFile(e.target.files?.[0] ?? null)} />
                <div className="spacer" />
                <button className="btn btn-primary" onClick={onUpload} disabled={!file || uploading}>
                  {uploading ? 'Uploading…' : 'Upload'}
                </button>
              </>
            ) : (
              <>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" checked={messageAll} onChange={e => setMessageAll(e.target.checked)} />
                  Message everyone with Slack IDs
                </label>
                <div className="spacer" />
                <button className="btn btn-primary" onClick={onRunAnalysis} disabled={uploading}>
                  {uploading ? 'Running…' : 'Run analysis'}
                </button>
              </>
            )}
          </div>
        </section>

        <section className="card">
          <h2>Queued notifications</h2>
          <div className="row" style={{ marginTop: 8 }}>
            <span className="badge">Filter</span>
            <select className="select" value={filter} onChange={e => setFilter(e.target.value)}>
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="denied">Denied</option>
            </select>
            <div className="spacer" />
          </div>
          <div style={{ marginTop: 12 }}>
            {notifications.map(n => (
              <NotificationRow key={n.id} n={n} onApprove={() => onApprove(n)} onDeny={onDeny} onSaveMessage={onSaveMessage} />
            ))}
            {notifications.length === 0 && <div className="list-empty">No notifications</div>}
          </div>
        </section>
      </div>
    </div>
  )
}

function NotificationRow({ n, onApprove, onDeny, onSaveMessage }: {
  n: Notification
  onApprove: (id: string) => void
  onDeny: (id: string) => void
  onSaveMessage: (id: string, message: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(n.message)
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, padding: 12, borderBottom: '1px solid #eee' }}>
      <div>
        <div style={{ fontWeight: 600 }}>{n.studentName} <span style={{ color: '#888' }}>({n.slackUserId})</span></div>
        {editing ? (
          <textarea value={text} onChange={e => setText(e.target.value)} style={{ width: '100%', minHeight: 60 }} />
        ) : (
          <div style={{ whiteSpace: 'pre-wrap' }}>{n.message}</div>
        )}
        <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
          {!editing && <button onClick={() => setEditing(true)}>Edit</button>}
          {editing && <button onClick={() => { setEditing(false); onSaveMessage(n.id, text) }}>Save</button>}
          {editing && <button onClick={() => { setEditing(false); setText(n.message) }}>Cancel</button>}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
        <span style={{ fontSize: 12, color: '#888' }}>{new Date(n.createdAtIso).toLocaleString()} — {n.status}</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => onApprove(n.id)} disabled={n.status !== 'pending'}>Approve</button>
          <button onClick={() => onDeny(n.id)} disabled={n.status !== 'pending'}>Deny</button>
        </div>
      </div>
    </div>
  )
}


