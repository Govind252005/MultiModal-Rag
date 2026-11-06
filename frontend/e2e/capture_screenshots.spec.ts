import { test, type Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'

const regularUser = { id: 'u1', email: 'analyst@enterprise.com', role: 'user', org_id: 'finance_dept' }
const localProvider = { provider: 'ollama', model: 'qwen3:4b', mode: 'local', status: 'active' }

const mockFiles = [
  { file: 'Q4_Financial_Audit.pdf', modality: 'document', chunks: 24, ingested_at: '2026-11-05' },
  { file: 'System_Architecture.pptx', modality: 'document', chunks: 18, ingested_at: '2026-11-05' },
  { file: 'Legal_Contract_Terms.docx', modality: 'document', chunks: 32, ingested_at: '2026-11-04' },
  { file: 'Market_Forecast_2026.xlsx', modality: 'document', chunks: 14, ingested_at: '2026-11-03' },
]

const mockSessions = [
  { id: 's1', title: 'Contract Liability & Audit Review', created_at: '2026-11-05', updated_at: '2026-11-05', message_count: 8, file_count: 3 },
  { id: 's2', title: 'Cloud Infrastructure Migration Analysis', created_at: '2026-11-04', updated_at: '2026-11-04', message_count: 4, file_count: 1 },
]

async function setupMocks(page: Page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const p = url.pathname

    if (p === '/api/auth/login' || p === '/api/auth/register') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ token: 'mock-jwt-token', user: regularUser }),
      })
      return
    }

    if (p === '/api/auth/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: regularUser }),
      })
      return
    }

    if (p === '/api/health') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ok',
          device: 'cuda',
          llm_available: true,
          llm_model: 'qwen3:4b',
          index: { text_items: 88, image_items: 12 },
        }),
      })
      return
    }

    if (p === '/api/llm/active') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(localProvider),
      })
      return
    }

    if (p === '/api/providers') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          default: 'ollama',
          providers: [
            { name: 'ollama', label: 'Local Qwen (Ollama)', local: true, model: 'qwen3:4b', has_key: true, available: true, supports_images: false, supports_streaming: true },
          ],
        }),
      })
      return
    }

    if (p === '/api/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sessions: mockSessions }),
      })
      return
    }

    if (p.startsWith('/api/sessions/')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 's1',
          title: 'Contract Liability & Audit Review',
          created_at: '2026-11-05',
          updated_at: '2026-11-05',
          messages: [],
          files: mockFiles,
        }),
      })
      return
    }

    if (p === '/api/files') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ files: mockFiles }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
}

test('Capture Screenshots for Stage 1 & 2', async ({ page }) => {
  const artifactDir = 'C:\\Users\\HP\\.gemini\\antigravity\\brain\\689acc0c-4d09-42bd-a9f2-46a2f6d7a7c3'
  fs.mkdirSync(artifactDir, { recursive: true })

  await setupMocks(page)

  // 1. Landing Page
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/landing')
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_1_landing_page.png'), fullPage: true })

  // 2. Sign In Page
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_2_sign_in_page.png') })

  // 3. Sign Up Page
  await page.getByRole('button', { name: 'Create one now' }).click()
  await page.waitForTimeout(300)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_3_sign_up_page.png') })

  // 4. Authenticated Dashboard (Light Theme)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByPlaceholder('you@example.com').fill(regularUser.email)
  await page.getByPlaceholder('Your password').fill('password123')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()
  await page.waitForSelector('text=Workspace Dashboard')
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_4_dashboard_light.png'), fullPage: true })

  // 5. Authenticated Dashboard (Dark Theme)
  await page.getByTitle(/switch to dark mode/i).click()
  await page.waitForTimeout(300)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_5_dashboard_dark.png'), fullPage: true })
})
