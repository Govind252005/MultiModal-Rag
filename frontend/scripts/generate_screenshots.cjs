const http = require('http');
const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');

const FRONTEND_DIR = path.resolve(__dirname, '..');
const DIST_DIR = path.join(FRONTEND_DIR, 'dist');
const SCREENSHOTS_DIR = path.join(FRONTEND_DIR, 'screenshots');

if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

function startServer(port) {
  const mimeTypes = {
    '.html': 'text/html',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
    '.ttf': 'font/ttf',
  };

  const server = http.createServer((req, res) => {
    let reqPath = req.url.split('?')[0];
    if (reqPath === '/') reqPath = '/index.html';
    let filePath = path.join(DIST_DIR, reqPath);

    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      filePath = path.join(DIST_DIR, 'index.html');
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || 'application/octet-stream';

    fs.readFile(filePath, (err, content) => {
      if (err) {
        res.writeHead(500);
        res.end('Server error');
      } else {
        res.writeHead(200, { 'Content-Type': contentType });
        res.end(content);
      }
    });
  });

  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => {
      console.log(`Preview server running at http://127.0.0.1:${port}`);
      resolve(server);
    });
  });
}

async function main() {
  const PORT = 4200;
  const server = await startServer(PORT);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2, // 2x Retina sharpness
  });

  const page = await context.newPage();
  page.on('console', (msg) => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', (err) => console.error('PAGE ERROR:', err.message));

  const mockSessionDetail = {
    id: 'sess_svvt_01',
    title: 'SVVT Practical File Analysis',
    files: [
      {
        id: 'f1',
        filename: 'SVVT_Practical_File_Govind.pdf',
        size: 1048576,
        modality: 'document',
        chunks: 12,
        uploaded_at: '2026-11-12T05:00:00Z',
      },
    ],
    messages: [
      {
        role: 'user',
        text: 'What is the aim of experiment 1 and 2 in the test plan?',
      },
      {
        role: 'assistant',
        used_llm: true,
        text:
          '### Experiment 1: Simulated Banking Application Test Cases\nThe primary objective is to design functional, negative, and boundary-oriented test cases for a simulated banking application and demonstrate selected cases in C++ [1].\n\n> **Aim Specification:**  \n> To design functional, negative and boundary-oriented test cases for a simulated banking application and demonstrate selected cases in C++ [1].\n\n### Experiment 2: Menu / Exit Test Case Design\nThe aim of Experiment 2 is to design test cases for menu selection, inventory reduction, and transaction termination conditions [2].\n\n| Test ID | Scenario | Input / Preconditions | Expected Result | Status |\n| :--- | :--- | :--- | :--- | :--- |\n| IN15 | Reduce stock | P02 - 2: qty >= 2 | Qty decreases | Verified [1] |\n| IN16 | Stock below zero | P02 - 20: qty 5 | Reject; unchanged | Verified [2] |\n| IN17 | At threshold | Qty = threshold | Low-stock alert | Verified [2] |\n| IN18 | Valid bill | 2 units at Rs20 | Total Rs40; stock -2 | Verified [1] |',
        citations: [
          {
            index: 1,
            id: 'src_doc_p1',
            file: 'SVVT_Practical_File_Govind.pdf',
            modality: 'document',
            source_type: 'pdf',
            page: 1,
            relative_relevance: 95,
            snippet:
              'EXPERIMENT 1: To design functional, negative and boundary-oriented test cases for a simulated banking application and demonstrate selected cases in C++...',
          },
          {
            index: 2,
            id: 'src_doc_p6',
            file: 'SVVT_Practical_File_Govind.pdf',
            modality: 'document',
            source_type: 'pdf',
            page: 6,
            relative_relevance: 92,
            snippet:
              'EXPERIMENT 2: System Specification and Test Case Design for Menu / Exit Test Cases (20)...',
          },
        ],
        metrics: {
          ttft_ms: 184,
          tokens_per_second: 42.6,
          retrieval_ms: 18,
          faithfulness_score: 0.98,
        },
      },
    ],
  };

  // Route API requests
  await page.route('**/api/**', async (route) => {
    const url = route.request().url();

    if (url.includes('/api/health')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ok',
          device: 'cuda',
          llm_model: 'qwen2.5:7b-instruct',
          llm_available: true,
          index: { text_items: 142, image_items: 2 },
        }),
      });
    }

    if (url.includes('/api/auth/me') || url.includes('/api/me')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: {
            id: 'usr_enterprise_01',
            email: 'lead.architect@defense.internal',
            role: 'admin',
            org_id: 'org_secure',
          },
        }),
      });
    }

    if (url.includes('/api/auth/login')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          token: 'mock_jwt_token_valid',
          user: {
            id: 'usr_enterprise_01',
            email: 'lead.architect@defense.internal',
            role: 'admin',
            org_id: 'org_secure',
          },
        }),
      });
    }

    if (url.includes('/api/providers/active')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'ollama',
          model: 'qwen2.5:7b-instruct',
          mode: 'local',
        }),
      });
    }

    if (url.includes('/api/providers')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          active: 'ollama',
          providers: [
            {
              name: 'ollama',
              label: 'Local Qwen (Ollama)',
              model: 'qwen2.5:7b-instruct',
              local: true,
              has_key: false,
            },
            {
              name: 'gemini',
              label: 'Google Gemini',
              model: 'gemini-1.5-pro',
              local: false,
              has_key: true,
            },
            {
              name: 'openai',
              label: 'OpenAI',
              model: 'gpt-4o',
              local: false,
              has_key: true,
            },
            {
              name: 'claude',
              label: 'Anthropic Claude',
              model: 'claude-3-5-sonnet',
              local: false,
              has_key: false,
            },
            {
              name: 'groq',
              label: 'Groq',
              model: 'llama-3.3-70b-versatile',
              local: false,
              has_key: false,
            },
          ],
        }),
      });
    }

    if (url.includes('/api/ollama/status')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          is_online: true,
          latency_ms: 12,
          default_model: 'qwen2.5:7b-instruct',
          models: [
            { name: 'qwen2.5:7b-instruct', size: 4700000000 },
          ],
        }),
      });
    }

    if (url.includes('/api/index/embeddings')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          dense_model: 'BAAI/bge-m3',
          dense_dimension: 1024,
          clip_model: 'openai/clip-vit-base-patch32',
          clip_dimension: 512,
        }),
      });
    }

    if (url.includes('/api/sessions/sess_svvt_01')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSessionDetail),
      });
    }

    if (url.endsWith('/api/sessions') || url.includes('/api/sessions?')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          sessions: [
            {
              id: 'sess_svvt_01',
              title: 'SVVT Practical File Analysis',
              file_count: 2,
              message_count: 6,
              created_at: '2026-11-12T05:00:00Z',
            },
            {
              id: 'sess_arch_02',
              title: 'Multimodal Neural Pipeline Specs',
              file_count: 4,
              message_count: 12,
              created_at: '2026-11-11T14:30:00Z',
            },
          ],
        }),
      });
    }

    if (url.includes('/api/source/')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'src_doc_p1',
          file: 'SVVT_Practical_File_Govind.pdf',
          modality: 'document',
          source_type: 'pdf',
          page: 1,
          chunk: 0,
          chunk_total: 12,
          full_text:
            'EXPERIMENT 1: To design functional, negative and boundary-oriented test cases for a simulated banking application and demonstrate selected cases in C++. Objective: Implement Equivalence Class Partitioning and Boundary Value Analysis for balance transaction routines.',
          media_url: '',
        }),
      });
    }

    if (url.includes('/content')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          filename: 'SVVT_Practical_File_Govind.pdf',
          modality: 'pdf',
          total_pages: 6,
          has_pages: true,
          pages: [
            {
              page: 1,
              text: 'SOFTWARE VERIFICATION, VALIDATION AND TESTING (SVVT)\n\nEXPERIMENT 1\nAim: To design functional, negative and boundary-oriented test cases for a simulated banking application and demonstrate selected cases in C++.\n\nTheory & Concepts:\nTest case design involves choosing inputs that test both intended features and edge cases. In this experiment, functional test cases verify standard balance deposit and withdrawal operations. Negative test cases verify that insufficient funds or invalid input characters are safely rejected. Boundary test cases focus on the maximum daily withdrawal threshold (Rs 50,000) and zero balance accounts.\n\nCode Implementation:\nDemonstrated using a C++ class Account with methods deposit(), withdraw(), and auditLog().',
            },
            {
              page: 6,
              text: 'EXPERIMENT 2: System Specification and Test Case Design for Menu / Exit Test Cases (20)\n\nAim: To design robust boundary-oriented test cases for menu selection, inventory reduction, and transaction termination conditions.\n\nTable 2.1: Test Specification\n| Test ID | Scenario | Input / Preconditions | Expected result | Actual result | Status |\n| IN15 | Reduce stock | P02 - 2: qty >= 2 | Qty decreases | As expected | Verified |\n| IN16 | Stock below zero | P02 - 20: qty 5 | Reject; unchanged | As expected | Verified |\n| IN17 | At threshold | Qty = threshold | Low-stock alert | Alert shown | Verified |\n| IN18 | Valid bill | 2 units at Rs20 | Total Rs40; stock -2 | Correct total | Verified |',
            },
          ],
        }),
      });
    }

    return route.fulfill({ status: 200, body: JSON.stringify({}) });
  });

  console.log('--- Screen 1: Landing Page ---');
  await page.goto(`http://127.0.0.1:${PORT}/`);
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.goto(`http://127.0.0.1:${PORT}/`);
  await page.waitForSelector('text=End-to-End Pipeline Execution Architecture', { timeout: 8000 });
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, '01_landing_page.png'),
    fullPage: false,
  });
  console.log('Saved 01_landing_page.png');

  console.log('--- Screen 2: Auth Page ---');
  await page.click('text=Sign In');
  await page.waitForSelector('text=Authenticate Session', { timeout: 8000 });
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, '02_auth_page.png'),
    fullPage: false,
  });
  console.log('Saved 02_auth_page.png');

  console.log('--- Screen 3: Workspace Chat and Composer ---');
  // Fill login credentials
  await page.fill('input[type="email"]', 'lead.architect@defense.internal');
  await page.fill('input[type="password"]', 'MasterPassphrase123!');
  await page.click('button[type="submit"]');

  // Wait for Dashboard
  await page.waitForSelector('text=SVVT Practical File Analysis', { timeout: 10000 });

  // Click on the recent session on dashboard
  await page.click('text=SVVT Practical File Analysis');

  // Wait for chat to render
  await page.waitForSelector('text=Simulated Banking Application', { timeout: 8000 });
  await page.waitForTimeout(800);

  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, '03_workspace_chat_and_composer.png'),
    fullPage: false,
  });
  console.log('Saved 03_workspace_chat_and_composer.png');

  console.log('--- Screen 4: Evidence Inspector Split View ---');
  // Click on citation [1] in the answer text to trigger split Document Viewer
  const citPill = await page.$('button[title*="supporting evidence source [1]"]');
  if (citPill) {
    await citPill.click();
  } else {
    await page.click('text="1"');
  }

  // Wait for Document Viewer
  await page.waitForSelector('text=SOFTWARE VERIFICATION', { timeout: 10000 });
  await page.waitForTimeout(1000);

  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, '04_evidence_inspector_split_view.png'),
    fullPage: false,
  });
  console.log('Saved 04_evidence_inspector_split_view.png');

  console.log('--- Switch to Dark Mode ---');
  await page.evaluate(() => {
    document.documentElement.classList.add('dark');
    localStorage.setItem('theme', 'dark');
  });
  await page.waitForTimeout(600);

  console.log('--- Screen 5: Evidence Inspector Split View (Dark Mode) ---');
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, '05_evidence_inspector_dark_mode.png'),
    fullPage: false,
  });
  console.log('Saved 05_evidence_inspector_dark_mode.png');

  console.log('--- Screen 6: Workspace Chat & Composer (Dark Mode) ---');
  // Close document viewer
  const closeBtn = await page.$('button[title="Close document viewer"]');
  if (closeBtn) {
    await closeBtn.click();
    await page.waitForTimeout(600);
  }
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, '06_workspace_chat_dark_mode.png'),
    fullPage: false,
  });
  console.log('Saved 06_workspace_chat_dark_mode.png');

  console.log('--- Screen 7: Models & Settings (Dark Mode) ---');
  await page.click('text=Models & Settings');
  await page.waitForSelector('text=Model Settings & Local AI Telemetry', { timeout: 8000 });
  await page.waitForTimeout(600);
  await page.screenshot({
    path: path.join(SCREENSHOTS_DIR, '07_model_settings_dark_mode.png'),
    fullPage: false,
  });
  console.log('Saved 07_model_settings_dark_mode.png');

  await browser.close();
  server.close();
  console.log('All screenshots captured successfully!');
}

main().catch((err) => {
  console.error('Screenshot generation error:', err);
  process.exit(1);
});
