import React, { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [receipts, setReceipts] = useState([])
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    if (token) {
      fetchReceipts()
    }
  }, [token])

  const handleLogin = async (e) => {
    e.preventDefault()
    try {
      const formData = new FormData()
      formData.append('username', email)
      formData.append('password', password)

      const response = await axios.post(`${API_URL}/auth/login`, formData)
      const accessToken = response.data.access_token

      localStorage.setItem('token', accessToken)
      setToken(accessToken)
      setMessage({ type: 'success', text: 'Login successful!' })
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Login failed' })
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setReceipts([])
    setMessage(null)
  }

  const fetchReceipts = async () => {
    try {
      const response = await axios.get(`${API_URL}/receipts`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setReceipts(response.data)
    } catch (error) {
      console.error('Failed to fetch receipts:', error)
    }
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!selectedFile) return

    setUploading(true)
    setMessage(null)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await axios.post(`${API_URL}/receipts`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      })

      setMessage({
        type: 'success',
        text: `Receipt uploaded! ID: ${response.data.receipt_id}, Status: ${response.data.status}`
      })
      setSelectedFile(null)
      fetchReceipts()
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Upload failed'
      })
    } finally {
      setUploading(false)
    }
  }

  const getStatusClass = (status) => {
    return `status-badge status-${status.toLowerCase()}`
  }

  if (!token) {
    return (
      <div>
        <div className="header">
          <div className="container">
            <h1>ExpenseOps</h1>
            <p>Receipt Processing System</p>
          </div>
        </div>

        <div className="container">
          <div className="card" style={{ maxWidth: '400px', margin: '0 auto' }}>
            <h2 style={{ marginBottom: '20px' }}>Login</h2>

            {message && (
              <div className={message.type}>
                {message.text}
              </div>
            )}

            <form onSubmit={handleLogin}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '8px' }}>Email</label>
                <input
                  type="email"
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px' }}>Password</label>
                <input
                  type="password"
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <button type="submit" className="button" style={{ width: '100%' }}>
                Login
              </button>
            </form>

            <div style={{ marginTop: '20px', textAlign: 'center', color: '#6b7280' }}>
              <small>
                Default admin: admin@expenseops.local / Admin123!
              </small>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="header">
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>ExpenseOps</h1>
            <p>Receipt Processing System</p>
          </div>
          <button onClick={handleLogout} className="button">
            Logout
          </button>
        </div>
      </div>

      <div className="container">
        {message && (
          <div className={message.type}>
            {message.text}
          </div>
        )}

        {/* Upload Form */}
        <div className="card">
          <h2 style={{ marginBottom: '16px' }}>Upload Receipt</h2>
          <form onSubmit={handleUpload}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <input
                  type="file"
                  className="input"
                  accept="image/*,.pdf"
                  onChange={(e) => setSelectedFile(e.target.files[0])}
                />
              </div>
              <button
                type="submit"
                className="button"
                disabled={!selectedFile || uploading}
              >
                {uploading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </form>
        </div>

        {/* Receipts List */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2>My Receipts ({receipts.length})</h2>
            <button onClick={fetchReceipts} className="button">
              Refresh
            </button>
          </div>

          {receipts.length === 0 ? (
            <p style={{ color: '#6b7280', textAlign: 'center', padding: '40px 0' }}>
              No receipts yet. Upload your first receipt above!
            </p>
          ) : (
            <div className="receipt-list">
              {receipts.map((receipt) => (
                <div key={receipt.id} className="receipt-item">
                  <div>
                    <div style={{ fontWeight: '500', marginBottom: '4px' }}>
                      {receipt.original_filename}
                    </div>
                    <div style={{ fontSize: '14px', color: '#6b7280' }}>
                      {receipt.merchant_name || 'Processing...'}
                      {receipt.total_amount && ` • $${receipt.total_amount}`}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className={getStatusClass(receipt.status)}>
                      {receipt.status}
                    </span>
                    <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                      #{receipt.id}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ textAlign: 'center', color: '#6b7280', marginTop: '40px' }}>
          <p>
            API Documentation:{' '}
            <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer"
               style={{ color: '#2563eb', textDecoration: 'none' }}>
              http://localhost:8000/docs
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}

export default App
