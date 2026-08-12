const { chromium } = require('playwright');
const path = require('path');

async function runVerification() {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // Set default timeout to 120s to account for 35s wait + slow LLM streaming
  page.setDefaultTimeout(120000);
  
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('requestfailed', request => {
    console.log(`REQUEST FAILED: ${request.url()} - ${request.failure().errorText}`);
  });
  
  try {
    // 1. Login
    console.log('[1/4] Navigating to /login...');
    await page.goto('http://localhost:3000/login');
    
    console.log('Filling login credentials...');
    await page.getByLabel('Email Address').fill('test@example.com');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    // Check if an error appears
    try {
      await page.waitForURL('http://localhost:3000/dashboard', { timeout: 5000 });
      console.log('Successfully redirected to /dashboard');
    } catch (e) {
      const errorEl = await page.locator('.text-red-400').first();
      if (await errorEl.isVisible()) {
        const errorText = await errorEl.textContent();
        throw new Error(`Login failed with UI error: ${errorText}`);
      }
      throw e;
    }
    
    // Wait for the Dashboard title to ensure the page loaded
    await page.waitForSelector('text=Welcome, test@example.com');
    
    // Retrieve and log the session ID created by AuthContext
    const sessionId = await page.evaluate(() => sessionStorage.getItem('sessionId'));
    console.log(`✓ Session created and stored by frontend. Session ID: ${sessionId}`);
    
    // 3. Upload File
    console.log('[3/4] Testing document upload UI...');
    await page.getByLabel('Document Title').fill('Aspirin Use Case Test');
    
    // Set file
    const fileInput = page.getByLabel('File (.txt)');
    await fileInput.setInputFiles(path.join(__dirname, '../test_upload.txt'));
    
    await page.getByRole('button', { name: 'Upload & Process' }).click();
    
    // Wait for success message which includes 'successfully'
    console.log('Waiting for upload success message...');
    await page.waitForSelector('text=successfully');
    const msg = await page.locator('text=successfully').textContent();
    console.log('Upload success:', msg.trim());
    
    // Wait a few seconds for Celery to process the document
    console.log('Waiting 5s to allow Celery worker to ingest and FAISS index to sync...');
    await page.waitForTimeout(5000); // 5s. Wait, verify_rag_stream.js showed that FAISS can take up to 30s because of the background sync.
    // Let's actually wait 35 seconds to be safe because of the 30s sync interval, 
    // or just run it and see if it fails (the LLM might hallucinate if retrieval is empty).
    // The user told me earlier I fixed a race condition by polling the document status in verify_rag_stream.
    // In the UI, we don't have polling implemented. We just navigate.
    // To ensure the test passes, I'll add a 35s wait here for the backend index to sync.
    console.log('Waiting 35s for FAISS background sync interval...');
    await page.waitForTimeout(35000);
    
    // 4. Search
    console.log('[4/4] Navigating to /search...');
    await page.getByRole('button', { name: 'Go to Search Interface →' }).click();
    await page.waitForURL('http://localhost:3000/search');
    
    console.log('Submitting query...');
    await page.getByPlaceholder('Ask a medical question...').fill('What is Aspirin used for?');
    await page.getByRole('button', { name: 'Search' }).click();
    
    // Wait for streaming to finish. The button changes from 'Thinking...' back to 'Search'
    console.log('Waiting for streaming to complete...');
    
    // Wait for button to be 'Search' and not disabled.
    // While streaming, button is disabled. Wait until it's enabled.
    await page.waitForFunction(() => {
        const btn = document.querySelector('button[type="submit"]');
        return btn && btn.textContent === 'Search' && !btn.disabled;
    }, { timeout: 60000 });
    
    console.log('Stream completed. Verifying results...');
    
    // Confirm Sources rendered
    const sourcesHeader = await page.locator('text=Retrieved Sources').isVisible();
    if (!sourcesHeader) {
        throw new Error('Sources section did not render');
    }
    
    const sourceItems = await page.locator('.font-medium.text-sm').count();
    console.log(`Found ${sourceItems} retrieved source(s)`);
    if (sourceItems === 0) {
        throw new Error('No retrieved sources found in UI');
    }
    
    // Print the generated answer
    const generatedAnswerHeader = await page.locator('text=Generated Answer').isVisible();
    if (!generatedAnswerHeader) {
        throw new Error('Generated Answer section did not render');
    }
    
    // The answer text is inside a div after the h3. 
    // In our DOM it's a div with whitespace-pre-wrap
    const answerContent = await page.locator('.whitespace-pre-wrap').textContent();
    console.log('--- Generated Answer ---');
    console.log(answerContent.trim());
    console.log('------------------------');
    
    console.log('✅ ALL UI TESTS PASSED SUCCESSFULLY');
    
  } catch (err) {
    console.error('❌ TEST FAILED:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

runVerification();
