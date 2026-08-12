const { chromium } = require('playwright');
const crypto = require('crypto');

async function runRegisterVerification() {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  page.setDefaultTimeout(60000); // 60s timeout
  
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  
  try {
    const randomSuffix = crypto.randomBytes(4).toString('hex');
    const testEmail = `newuser_${randomSuffix}@example.com`;
    const testPassword = 'password123';
    
    // 1. Navigate to /login and click "Sign up"
    console.log('[1/4] Navigating to /login...');
    await page.goto('http://localhost:3000/login');
    
    console.log('[2/4] Clicking "Sign up" link...');
    await page.click('text="Sign up"');
    
    // Wait for URL to change to /register
    await page.waitForURL('http://localhost:3000/register');
    console.log('Successfully navigated to /register');
    
    // 3. Fill registration form
    console.log(`[3/4] Filling registration form with ${testEmail}...`);
    await page.getByLabel('Full Name').fill('Playwright Test User');
    await page.getByLabel('Email Address').fill(testEmail);
    await page.getByLabel('Password').fill(testPassword);
    
    console.log('Submitting registration form...');
    await page.getByRole('button', { name: 'Sign Up' }).click();
    
    // 4. Verify automatic login and redirect to dashboard
    console.log('[4/4] Waiting for automatic login and redirect to /dashboard...');
    
    try {
      await page.waitForURL('http://localhost:3000/dashboard', { timeout: 20000 });
      console.log('✅ SUCCESS: Registered, automatically logged in, and redirected to /dashboard');
    } catch (e) {
      await page.screenshot({ path: 'register_fail.png' });
      console.log('Took screenshot of failure to frontend/register_fail.png');
      const errorEl = await page.locator('.text-red-400').first();
      if (await errorEl.isVisible()) {
        const errorText = await errorEl.textContent();
        throw new Error(`Registration failed with UI error: ${errorText}`);
      }
      throw e;
    }
    
  } catch (error) {
    console.error('❌ VERIFICATION FAILED:', error);
    process.exit(1);
  } finally {
    console.log('Closing browser...');
    await browser.close();
  }
}

runRegisterVerification();
