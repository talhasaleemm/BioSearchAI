import { useEffect, useState } from 'react'
import { mockSessions, mockActions } from './mockData.js'

const API_BASE = 'http://localhost:8000'

async function request(config) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(config.headers || {}),
  }

  const response = await fetch(`${API_BASE}${config.url}`, {
    method: config.method || 'GET',
    headers,
    body: config.body ? JSON.stringify(config.body) : undefined,
    credentials: 'omit',
  })

  if (!response.ok) {
    const error = new Error(`Request failed: ${response.status}`)
    error.status = response.status
    throw error
  }

  return await response.json()
}

export const login = async (credentials) => {
  return request({ method: 'POST', url: '/auth/login', body: credentials })
}

export const register = async (credentials) => {
  return request({ method: 'POST', url: '/auth/register', body: credentials })
}

export const getCurrentUser = async () => {
  return request({ method: 'GET', url: '/auth/me' })
}

export const getSessions = async () => {
  try {
    return await request({ method: 'GET', url: '/history/' })
  } catch (error) {
    console.warn('Backend unavailable for sessions, using mock data')
    return mockSessions
  }
}

export const getSessionActions = async (sessionId) => {
  try {
    const data = await request({ method: 'GET', url: `/history/${sessionId}/actions` })
    return data
  } catch (error) {
    console.warn(`Backend unavailable for session ${sessionId}, using mock data`)
    return mockActions.filter((action) => action.session_id === Number(sessionId))
  }
}

export { mockSessions, mockActions }
