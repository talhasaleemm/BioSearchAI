'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect, useState, useRef } from 'react';
import { API_URL } from '@/lib/api';

export default function SearchPage() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();

  const [query, setQuery] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<any[]>([]);
  const [error, setError] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    // Auto-scroll to bottom of answer as it streams
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [answer]);

  if (isLoading || !isAuthenticated) {
    return <div className="min-h-screen flex items-center justify-center bg-[var(--background)] text-white">Loading...</div>;
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsStreaming(true);
    setAnswer('');
    setSources([]);
    setError('');

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

      const token = sessionStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/v1/rag/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query,
          top_k: 5,
          temperature: 0.2,
        }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Failed to start stream: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          
          // SSE events are separated by double newlines
          let boundaryIdx;
          while ((boundaryIdx = buffer.indexOf('\n\n')) >= 0) {
            const event = buffer.substring(0, boundaryIdx);
            buffer = buffer.substring(boundaryIdx + 2);
            
            if (event.startsWith('data: ')) {
              const dataStr = event.substring(6);
              if (!dataStr) continue;

              try {
                // Try parsing as JSON first (for the sources payload)
                const parsed = JSON.parse(dataStr);
                if (parsed.type === 'sources') {
                  const uniqueSources = Array.from(new Map(parsed.sources.map((s: any) => [s.text, s])).values());
                  setSources(uniqueSources);
                } else {
                  setAnswer((prev) => prev + dataStr);
                }
              } catch (e) {
                // Not JSON, this is a raw token from the LLM
                setAnswer((prev) => prev + dataStr);
              }
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setError('Request timed out. The server took too long to respond.');
      } else {
        setError(err.message || 'An error occurred during search');
      }
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[var(--background)] text-white">
      {/* Header */}
      <header className="p-6 border-b border-white/10 flex justify-between items-center backdrop-blur-xl bg-black/20 z-10 sticky top-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">BioSearchAI</h1>
          <p className="text-sm text-slate-400">Semantic RAG Search</p>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={() => router.push('/dashboard')}
            className="px-4 py-2 hover:bg-white/5 rounded-lg transition-colors text-slate-300"
          >
            Dashboard
          </button>
          <button 
            onClick={logout}
            className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-colors border border-red-500/20"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col max-w-5xl w-full mx-auto p-6 relative">
        <div className="absolute top-[20%] left-[-20%] w-[50%] h-[50%] rounded-full bg-[var(--primary)]/10 blur-[120px] pointer-events-none" />

        {/* Results Area */}
        <div className="flex-1 overflow-y-auto mb-6 space-y-8 pr-2 relative z-10 min-h-[50vh]">
          {error && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          {(!answer && !isStreaming && !error) && (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 mt-20">
              <div className="w-16 h-16 mb-4 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                <svg className="w-8 h-8 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
              </div>
              <p className="text-lg">Ask a question about the ingested medical documents</p>
            </div>
          )}

          {sources.length > 0 && (
            <div className="animate-fade-in-up">
              <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Retrieved Sources</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sources.map((source, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-white/5 border border-white/10 backdrop-blur-sm">
                    <div className="font-medium text-sm text-[var(--primary)] mb-1">
                      {source.document?.title || 'Unknown Document'}
                    </div>
                    <div className="text-xs text-slate-400 mb-2 font-mono">
                      {source.document?.source_id ? `Source: ${source.document.source_id}` : 'Local File'} • Score: {source.similarity_score}
                    </div>
                    <p className="text-sm text-slate-300 line-clamp-3">{source.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {answer && !answer.includes('Answer generation is currently unavailable') && (
            <div className="animate-fade-in-up">
              <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Generated Answer</h3>
              <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm prose prose-invert max-w-none text-slate-200 leading-relaxed">
                {/* Note: In a real app, we'd use react-markdown here to parse the LLM output properly */}
                <div className="whitespace-pre-wrap">{answer}</div>
                {isStreaming && <span className="inline-block w-2 h-4 bg-[var(--primary)] ml-1 animate-pulse" />}
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="sticky bottom-6 z-20">
          <form onSubmit={handleSearch} className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isStreaming}
              placeholder="Ask a medical question..."
              className="w-full pl-6 pr-32 py-4 rounded-2xl bg-black/40 border border-white/20 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent transition-all shadow-2xl backdrop-blur-xl disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isStreaming || !query.trim()}
              className="absolute right-2 top-2 bottom-2 px-6 rounded-xl bg-gradient-to-r from-[var(--primary)] to-[var(--primary-hover)] text-white font-medium shadow-lg hover:shadow-[var(--primary)]/40 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isStreaming ? 'Thinking...' : 'Search'}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

