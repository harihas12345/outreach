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

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [filter, setFilter] = useState('pending')

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
      const presignResp = await fetch(PRESIGN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fileName: file.name, prefix: S3_PREFIX }),
      })
      const { presigned, key } = await presignResp.json()

      const formData = new FormData()
      Object.entries(presigned.fields).forEach(([k, v]) => formData.append(k, String(v)))
      formData.append('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
      formData.append('file', file)
      const s3Post = await fetch(presigned.url, { method: 'POST', body: formData })
      if (!s3Post.ok) throw new Error('S3 upload failed')
      setFile(null)
      // Orchestrator fires on S3 event; give it a moment then refresh
      setTimeout(() => void refresh(), 3000)
    } catch (e) {
      console.error(e)
      alert('Upload failed')
    } finally {
      setUploading(false)
    }
  }, [file, refresh])

  const onApprove = useCallback(async (id: string) => {
    await fetch(`${BACKEND_URL.replace(/\/$/, '')}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notificationId: id, decision: 'approve' }),
    })
    void refresh()
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
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 24, fontFamily: 'system-ui, sans-serif' }}>
      <h1>ACI Progress</h1>
      <section style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8, marginBottom: 24 }}>
        <h2>Upload weekly Excel</h2>
        <input type="file" accept=".xlsx" onChange={e => setFile(e.target.files?.[0] ?? null)} />
        <button onClick={onUpload} disabled={!file || uploading} style={{ marginLeft: 12 }}>
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </section>

      <section style={{ border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
        <h2>Queued notifications</h2>
        <label>
          Filter:
          <select value={filter} onChange={e => setFilter(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="denied">Denied</option>
          </select>
        </label>
        <div style={{ marginTop: 12 }}>
          {notifications.map(n => (
            <NotificationRow key={n.id} n={n} onApprove={onApprove} onDeny={onDeny} onSaveMessage={onSaveMessage} />
          ))}
          {notifications.length === 0 && <div>No notifications</div>}
        </div>
      </section>
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


