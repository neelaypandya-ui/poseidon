import { useState, useCallback, useEffect } from 'react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface User {
  id: number
  username: string
  email: string
  role: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}

const TOKEN_KEY = 'poseidon_token'

export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    return { user: null, token, isAuthenticated: false }
  })

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await axios.post(`${API_URL}/api/v1/auth/login`, { username, password })
    const token = data.access_token
    localStorage.setItem(TOKEN_KEY, token)
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
    setAuthState({ user: data.user, token, isAuthenticated: true })
    return data.user
  }, [])

  const register = useCallback(async (username: string, email: string, password: string) => {
    const { data } = await axios.post(`${API_URL}/api/v1/auth/register`, { username, email, password })
    return data.user
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    delete axios.defaults.headers.common['Authorization']
    setAuthState({ user: null, token: null, isAuthenticated: false })
  }, [])

  const fetchMe = useCallback(async () => {
    try {
      const token = localStorage.getItem(TOKEN_KEY)
      if (!token) return
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      const { data } = await axios.get(`${API_URL}/api/v1/auth/me`)
      setAuthState({ user: data, token, isAuthenticated: true })
    } catch {
      localStorage.removeItem(TOKEN_KEY)
      delete axios.defaults.headers.common['Authorization']
    }
  }, [])

  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  return { ...authState, login, register, logout }
}
