'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';

export default function DashboardPage() {
  const { user, sessionId, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [pubmedQuery, setPubmedQuery] = useState('');
  const [pubmedResults, setPubmedResults] = useState<any[]>([]);
  const [isSearchingPubMed, setIsSearchingPubMed] = useState(false);
  const [ingestingPmid, setIngestingPmid] = useState<string | null>(null);
  const [pubmedMessage, setPubmedMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);


  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return <div className="min-h-screen flex items-center justify-center bg-[var(--background)] text-white">Loading...</div>;
  }

  
  const handlePubmedSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pubmedQuery) return;
    
    setIsSearchingPubMed(true);
    setPubmedMessage(null);
    setPubmedResults([]);

    try {
      const response = await fetchApi('/api/v1/documents/pubmed-search', {
        method: 'POST',
        body: JSON.stringify({ query: pubmedQuery, max_results: 5 }),
      });
      setPubmedResults(response.results || []);
      if (!response.results || response.results.length === 0) {
        setPubmedMessage({ type: 'success', text: 'No results found.' });
      }
    } catch (err: any) {
      setPubmedMessage({ type: 'error', text: err.message || 'Failed to search PubMed' });
    } finally {
      setIsSearchingPubMed(false);
    }
  };

  const handlePubmedIngest = async (pmid: string) => {
    setIngestingPmid(pmid);
    setPubmedMessage(null);
    try {
      const response = await fetchApi('/api/v1/documents/pubmed-ingest', {
        method: 'POST',
        body: JSON.stringify({ pmid, session_id: sessionId }),
      });
      setPubmedMessage({ type: 'success', text: PubMed abstract queued successfully! (ID: ) });
    } catch (err: any) {
      setPubmedMessage({ type: 'error', text: err.message || 'Failed to ingest PubMed abstract' });
    } finally {
      setIngestingPmid(null);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title) {
      setMessage({ type: 'error', text: 'Please provide a title and select a file.' });
      return;
    }

    setIsUploading(true);
    setMessage(null);

    try {
      // Read file content as text
      const content = await file.text();

      // Send JSON payload
      const response = await fetchApi('/api/v1/documents/ingest', {
        method: 'POST',
        body: JSON.stringify({
          title,
          source_type: 'upload',
          source_url: sourceUrl || file.name,
          content,
          session_id: sessionId, // Use real session ID
        }),
      });

      setMessage({ type: 'success', text: `Document queued successfully! (ID: ${response.id})` });
      setFile(null);
      setTitle('');
      setSourceUrl('');
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to upload document' });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen p-8 bg-[var(--background)] text-white relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-[var(--primary)]/10 blur-[120px] pointer-events-none" />
      
      <div className="max-w-4xl mx-auto relative z-10">
        <div className="flex justify-between items-center mb-12">
          <div>
            <h1 className="text-3xl font-bold tracking-tight mb-2">Dashboard</h1>
            <p className="text-slate-400">Welcome, {user?.email}</p>
          </div>
          <button 
            onClick={logout}
            className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-colors border border-red-500/20"
          >
            Sign Out
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Upload Section */}
          <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl shadow-xl">
            <h2 className="text-xl font-semibold mb-6">Ingest Document</h2>
            
            {message && (
              <div className={`mb-6 p-4 rounded-lg border text-sm ${
                message.type === 'success' 
                  ? 'bg-green-500/10 border-green-500/20 text-green-400' 
                  : 'bg-red-500/10 border-red-500/20 text-red-400'
              }`}>
                {message.text}
              </div>
            )}

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label htmlFor="document-title" className="block text-sm font-medium text-slate-300 mb-1.5">Document Title</label>
                <input
                  id="document-title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg bg-black/20 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent transition-all"
                  placeholder="e.g., Clinical Trial Results"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Source URL (Optional)</label>
                <input
                  type="text"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg bg-black/20 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent transition-all"
                  placeholder="https://pubmed.ncbi.nlm.nih.gov/..."
                />
              </div>

              <div>
                <label htmlFor="document-file" className="block text-sm font-medium text-slate-300 mb-1.5">File (.txt)</label>
                <input
                  id="document-file"
                  type="file"
                  accept=".txt,.md"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full px-4 py-2.5 rounded-lg bg-black/20 border border-white/10 text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-[var(--primary)]/20 file:text-[var(--primary)] hover:file:bg-[var(--primary)]/30 transition-all cursor-pointer"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={isUploading || !file || !title}
                className="w-full py-3 px-4 mt-2 rounded-lg bg-gradient-to-r from-[var(--primary)] to-[var(--primary-hover)] text-white font-medium shadow-lg shadow-[var(--primary)]/25 hover:shadow-[var(--primary)]/40 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUploading ? 'Ingesting...' : 'Upload & Process'}
              </button>
            </form>
          </div>

          {/* Navigation to Search */}
          <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl shadow-xl flex flex-col justify-between">
            <div>
              <h2 className="text-xl font-semibold mb-4">Search & Chat</h2>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                Ready to explore the ingested medical documents? Navigate to the search interface to run semantic queries and generate RAG responses.
              </p>
            </div>
            <button
              onClick={() => router.push('/search')}
              className="w-full py-3 px-4 rounded-lg bg-white/10 hover:bg-white/15 text-white font-medium transition-all duration-200 border border-white/5"
            >
              Go to Search Interface →
            </button>
          </div>
        </div>

        {/* PubMed Integration Section */}
        <div className="mt-8 p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xl shadow-xl">
          <h2 className="text-xl font-semibold mb-6">Search & Ingest from PubMed</h2>
          
          {pubmedMessage && (
            <div className={mb-6 p-4 rounded-lg border text-sm }>
              {pubmedMessage.text}
            </div>
          )}

          <form onSubmit={handlePubmedSearch} className="flex gap-4 mb-8">
            <input
              type="text"
              value={pubmedQuery}
              onChange={(e) => setPubmedQuery(e.target.value)}
              className="flex-1 px-4 py-2.5 rounded-lg bg-black/20 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent transition-all"
              placeholder="e.g., BRCA1 breast cancer"
              required
            />
            <button
              type="submit"
              disabled={isSearchingPubMed || !pubmedQuery}
              className="px-6 py-2.5 rounded-lg bg-white/10 hover:bg-white/15 text-white font-medium transition-all duration-200 border border-white/5 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {isSearchingPubMed ? 'Searching...' : 'Search PubMed'}
            </button>
          </form>

          {pubmedResults.length > 0 && (
            <div className="space-y-4">
              {pubmedResults.map((result, idx) => (
                <div key={result.pmid + idx} className="p-4 rounded-lg bg-black/20 border border-white/5 flex flex-col md:flex-row justify-between gap-4">
                  <div className="flex-1">
                    <h3 className="font-medium text-white mb-1">{result.title}</h3>
                    <div className="text-xs text-slate-400 mb-2">PMID: {result.pmid} | Year: {result.year || 'N/A'}</div>
                    <p className="text-sm text-slate-300 line-clamp-3">{result.abstract}</p>
                  </div>
                  <div className="flex items-start md:items-center">
                    <button
                      onClick={() => handlePubmedIngest(result.pmid)}
                      disabled={ingestingPmid === result.pmid}
                      className="px-4 py-2 rounded-lg bg-[var(--primary)]/20 text-[var(--primary)] hover:bg-[var(--primary)]/30 font-medium transition-all duration-200 disabled:opacity-50 whitespace-nowrap"
                    >
                      {ingestingPmid === result.pmid ? 'Ingesting...' : 'Ingest'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
