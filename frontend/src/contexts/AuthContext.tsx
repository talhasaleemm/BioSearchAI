'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { API_URL } from '@/lib/api';

interface User {
  email: string;
}

interface AuthContextType {
  user: User | null;
  sessionId: number | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, email: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check for existing token on mount
    const token = sessionStorage.getItem('token');
    const email = sessionStorage.getItem('email');
    const savedSessionId = sessionStorage.getItem('sessionId');
    
    if (token && email) {
      setUser({ email });
      if (savedSessionId) {
        setSessionId(parseInt(savedSessionId, 10));
      } else {
        // Create session
        createSession(token).then(id => {
            if(id) {
                setSessionId(id);
                sessionStorage.setItem('sessionId', id.toString());
            }
        });
      }
    }
    setIsLoading(false);
  }, []);

  const createSession = async (token: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/sessions/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        return data.id;
      }
    } catch(e) {
      console.error("Failed to create session", e);
    }
    return null;
  };

  const login = async (token: string, email: string) => {
    sessionStorage.setItem('token', token);
    sessionStorage.setItem('email', email);
    setUser({ email });
    const id = await createSession(token);
    if(id) {
        setSessionId(id);
        sessionStorage.setItem('sessionId', id.toString());
    }
  };

  const logout = () => {
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('email');
    sessionStorage.removeItem('sessionId');
    setUser(null);
    setSessionId(null);
  };

  return (
    <AuthContext.Provider value={{ user, sessionId, isAuthenticated: !!user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
