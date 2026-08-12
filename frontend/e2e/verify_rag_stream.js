const fs = require('fs');

const API_URL = 'http://localhost:8000';

async function main() {
  console.log('--- E2E Programmatic Verification ---');
  
  // 1. Authenticate
  console.log('\n[1/3] Authenticating as test@example.com...');
  const tokenRes = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'test@example.com', password: 'password123' })
  });

  if (!tokenRes.ok) {
    throw new Error(`Auth failed: ${await tokenRes.text()}`);
  }

  const { access_token } = await tokenRes.json();
  console.log('✓ Authentication successful, token received.');

  // 1.5 Create Session
  console.log('\n[1.5/3] Creating search session...');
  const sessionRes = await fetch(`${API_URL}/api/v1/sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${access_token}`
    }
  });

  if (!sessionRes.ok) {
    throw new Error(`Session creation failed: ${await sessionRes.text()}`);
  }

  const { id: sessionId } = await sessionRes.json();
  console.log(`✓ Session created successfully. Session ID: ${sessionId}`);

  // 2. Upload Document
  console.log('\n[2/3] Uploading dummy document...');
  const dummyContent = 'Aspirin is a nonsteroidal anti-inflammatory drug (NSAID) used to reduce pain, fever, or inflammation.';
  
  const ingestRes = await fetch(`${API_URL}/api/v1/documents/ingest`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({
      title: 'Aspirin Overview',
      source_type: 'upload',
      source_url: 'dummy.txt',
      content: dummyContent,
      session_id: sessionId
    })
  });

  if (!ingestRes.ok) {
    throw new Error(`Ingest failed: ${await ingestRes.text()}`);
  }

  const ingestData = await ingestRes.json();
  console.log(`✓ Document queued successfully. Document ID: ${ingestData.id}`);

  // Wait for Celery worker to process the document
  console.log('\n[2.5/3] Waiting for document to be processed by Celery worker...');
  const { execSync } = require('child_process');
  let isProcessed = false;
  let attempts = 0;
  
  while (!isProcessed && attempts < 40) { // 200s timeout to allow for first-time model download
    attempts++;
    try {
      const output = execSync(`docker-compose exec -T web python -c "from app.core.db import SessionLocal; from app.models.user import User; from app.models.search_session import SearchSession; from app.models.document import Document; from app.models.chunk import Chunk; from app.models.session_action import SessionAction; db = SessionLocal(); doc = db.query(Document).filter(Document.id == ${ingestData.id}).first(); print(doc.status if doc else 'not_found')"`, { encoding: 'utf-8' }).trim();
      if (output === 'processed') {
        isProcessed = true;
        console.log('✓ Document status is processed.');
      } else if (output === 'failed') {
        throw new Error('Document processing failed in Celery worker.');
      } else {
        process.stdout.write('.');
        await new Promise(r => setTimeout(r, 5000));
      }
    } catch (e) {
      console.error(`\nError checking DB: ${e.message}`);
      await new Promise(r => setTimeout(r, 5000));
    }
  }

  if (!isProcessed) {
    throw new Error('Timeout waiting for document to be processed by Celery worker.');
  }

  // Poll FAISS sync via search endpoint
  console.log('\n[2.6/3] Waiting for FAISS index to sync (polling search endpoint)...');
  let isSynced = false;
  attempts = 0;
  while (!isSynced && attempts < 10) { // 50s timeout (covers the 30s sync interval)
    attempts++;
    const searchRes = await fetch(`${API_URL}/api/v1/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
      },
      body: JSON.stringify({ query: 'aspirin', top_k: 1 })
    });
    
    if (searchRes.ok) {
      const searchData = await searchRes.json();
      if (searchData.results_count > 0) {
        isSynced = true;
        console.log('✓ FAISS sync confirmed. Document is searchable.');
      } else {
        process.stdout.write('.');
        await new Promise(r => setTimeout(r, 5000));
      }
    } else {
      process.stdout.write('!');
      await new Promise(r => setTimeout(r, 5000));
    }
  }

  if (!isSynced) {
    throw new Error('Timeout waiting for FAISS index to sync.');
  }

  // 3. RAG Query
  console.log('\n[3/3] Initiating RAG Stream Query for "What is aspirin used for?"...');
  
  const ragRes = await fetch(`${API_URL}/api/v1/rag/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${access_token}`
    },
    body: JSON.stringify({
      query: 'What is aspirin used for?',
      top_k: 5,
      temperature: 0.1
    })
  });

  if (!ragRes.ok) {
    throw new Error(`RAG failed: ${await ragRes.text()}`);
  }

  // Process the SSE stream (same manual logic as the frontend)
  const reader = ragRes.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let done = false;
  
  let sourcesReceived = false;
  let fullAnswer = '';

  while (!done) {
    const { value, done: readerDone } = await reader.read();
    done = readerDone;
    if (value) {
      const chunk = decoder.decode(value, { stream: true });
      const events = chunk.split('\n\n');
      
      for (const event of events) {
        if (event.startsWith('data: ')) {
          const dataStr = event.substring(6);
          if (!dataStr) continue;

          try {
            const parsed = JSON.parse(dataStr);
            if (parsed.type === 'sources') {
              console.log(`✓ Received Sources Metadata: ${parsed.sources.length} sources found.`);
              sourcesReceived = true;
            } else {
              fullAnswer += dataStr;
              process.stdout.write(dataStr);
            }
          } catch (e) {
            // Not JSON -> raw token
            fullAnswer += dataStr;
            process.stdout.write(dataStr);
          }
        }
      }
    }
  }

  console.log('\n\n✓ Stream complete.');
  console.log('--- Verification Successful ---');
}

main().catch(err => {
  console.error('\n❌ Verification Failed:', err);
  process.exit(1);
});
