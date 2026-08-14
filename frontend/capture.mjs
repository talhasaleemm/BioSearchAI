import { chromium } from 'playwright';
import path from 'path';

(async () => {
  const browser = await chromium.launch();
  // Set viewport to the width of the diagram container plus some padding
  const page = await browser.newPage({ viewport: { width: 1480, height: 900 } });
  
  const filePath = path.resolve('../biosearchai_architecture.html');
  await page.goto(`file://${filePath}`);
  
  // Wait for Google Fonts and FontAwesome/SimpleIcons to fully load
  await page.waitForTimeout(3000); 
  
  // Capture screenshot as JPEG
  await page.screenshot({ 
      path: '../biosearchai_architecture.jpg', 
      type: 'jpeg', 
      quality: 100, 
      fullPage: true 
  });
  
  await browser.close();
  console.log("Screenshot saved as biosearchai_architecture.jpg in the root directory!");
})();
