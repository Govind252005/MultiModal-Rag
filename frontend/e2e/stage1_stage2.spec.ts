import { expect, test, type Page } from '@playwright/test'

const regularUser = { id: 'u1', email: 'analyst@enterprise.com', role: 'user', org_id: 'finance_dept' }
const adminUser = { id: 'a1', email: 'admin@enterprise.com', role: 'admin', org_id: 'corp_hq' }

const localProvider = { provider: 'ollama', model: 'qwen3:4b', mode: 'local', status: 'active' }
const cloudProvider = { provider: 'gemini', model: 'gemini-1.5-pro', mode: 'cloud', status: 'active' }

async function setupMocks(page: Page, options: { user?: any; provider?: any; files?: any[]; sessions?: any[] } = {}) {
  const activeUser = options.user || regularUser
  const activeProv = options.provider || localProvider
  const mockFiles = options.files || [
    { file: 'Q4_Financial_Audit.pdf', modality: 'document', chunks: 24, ingested_at: '2026-11-05' },
    { file: 'System_Architecture.pptx', modality: 'document', chunks: 18, ingested_at: '2026-11-05' },
  ]
  const mockSessions = options.sessions || [
    { id: 's1', title: 'Contract Liability Inquiry', created_at: '2026-11-05', updated_at: '2026-11-05', message_count: 6, file_count: 2 },
  ]

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/api/auth/login') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ token: 'mock-jwt-token', user: activeUser }),
      })
      return
    }

    if (path === '/api/auth/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: activeUser }),
      })
      return
    }

    if (path === '/api/health') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ok',
          device: 'cuda',
          llm_available: true,
          llm_model: 'qwen3:4b',
          index: { text_items: 42, image_items: 8 },
        }),
      })
      return
    }

    if (path === '/api/llm/active') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(activeProv),
      })
      return
    }

    if (path === '/api/providers') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          default: 'ollama',
          providers: [
            { name: 'ollama', label: 'Local Qwen (Ollama)', local: true, model: 'qwen3:4b', has_key: true, available: true, supports_images: false, supports_streaming: true },
            { name: 'gemini', label: 'Google Gemini', local: false, model: 'gemini-1.5-pro', has_key: true, available: true, supports_images: true, supports_streaming: true },
          ],
        }),
      })
      return
    }

    if (path === '/api/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sessions: mockSessions }),
      })
      return
    }

    if (path.startsWith('/api/sessions/')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 's1',
          title: 'Contract Liability Inquiry',
          created_at: '2026-11-05',
          updated_at: '2026-11-05',
          messages: [],
          files: mockFiles,
        }),
      })
      return
    }

    if (path === '/api/files') {
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

test('Stage 2: Landing page renders and navigates to sign in', async ({ page }) => {
  await setupMocks(page)
  // Navigate to landing page directly
  await page.goto('/landing')
  await expect(page.getByRole('heading', { name: /ground ai answers in verified/i })).toBeVisible()
  await expect(page.getByText(/enterprise document intelligence/i)).toBeVisible()
  await expect(page.getByText(/verifiable evidence/i)).toBeVisible()

  // Click Sign In button from landing page
  await page.getByRole('button', { name: 'Sign In' }).first().click()
  await expect(page.getByRole('heading', { name: /sign in to multimodal rag/i })).toBeVisible()
  await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
})

test('Stage 1 & 2: Authenticated Dashboard renders genuine metrics from backend', async ({ page }) => {
  await setupMocks(page)
  await page.goto('/')

  // Sign in
  await page.getByPlaceholder('you@example.com').fill(regularUser.email)
  await page.getByPlaceholder('Your password').fill('password123')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()

  // Verify Dashboard Shell
  await expect(page.getByRole('heading', { name: 'Workspace Dashboard' })).toBeVisible()
  await expect(page.getByText('finance_dept')).toBeVisible()

  // Verify genuine metrics: 50 total chunks (42 text + 8 image), 2 files, 1 conversation
  await expect(page.getByText('50')).toBeVisible() // 42+8 total vector chunks
  await expect(page.getByText('42 text · 8 visual')).toBeVisible()
  await expect(page.getByText('Q4_Financial_Audit.pdf').first()).toBeVisible()
  await expect(page.getByText('Contract Liability Inquiry').first()).toBeVisible()

  // Verify Genuine Local Processing Status Badge
  await expect(page.getByText(/100% on-premise processing active/i)).toBeVisible()
  await expect(page.getByText(/local processing active/i).first()).toBeVisible()

  // Administration link should NOT be visible for regular user
  await expect(page.getByRole('button', { name: 'Administration' })).not.toBeVisible()
})

test('Stage 1: Administrator user sees Administration section in sidebar', async ({ page }) => {
  await setupMocks(page, { user: adminUser })
  await page.goto('/')

  await page.getByPlaceholder('you@example.com').fill(adminUser.email)
  await page.getByPlaceholder('Your password').fill('adminpass123')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()

  // Administration link should be visible for admin
  await expect(page.getByRole('button', { name: 'Administration' })).toBeVisible()
  await page.getByRole('button', { name: 'Administration' }).click()
  await expect(page.getByRole('heading', { name: 'Enterprise Administration' })).toBeVisible()
  await expect(page.getByText(/role-based access control enforced/i)).toBeVisible()
})

test('Stage 1: Cloud provider does not falsely claim 100% On-Premise', async ({ page }) => {
  await setupMocks(page, { provider: cloudProvider })
  await page.goto('/')

  await page.getByPlaceholder('you@example.com').fill(regularUser.email)
  await page.getByPlaceholder('Your password').fill('password123')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()

  // Should display Cloud AI Connected, NOT 100% On-Premise
  await expect(page.getByText(/cloud ai connected/i)).toBeVisible()
  await expect(page.getByText(/100% on-premise/i)).not.toBeVisible()
  await expect(page.getByText(/cloud connected/i).first()).toBeVisible()
})

test('Stage 2: Dashboard quick action navigates to AI Chat', async ({ page }) => {
  await setupMocks(page)
  await page.goto('/')

  await page.getByPlaceholder('you@example.com').fill(regularUser.email)
  await page.getByPlaceholder('Your password').fill('password123')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()

  // Click "Start AI Chat"
  await page.getByRole('button', { name: 'Start AI Chat' }).click()

  // Should be in Chat view with composer visible
  await expect(page.getByRole('button', { name: 'New chat' })).toBeVisible()
})
