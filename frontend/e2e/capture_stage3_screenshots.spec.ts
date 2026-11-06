import { expect, test, type Page } from '@playwright/test'
import path from 'path'

const regularUser = { id: 'u1', email: 'analyst@enterprise.com', role: 'user', org_id: 'finance_dept' }
const localProvider = { provider: 'ollama', model: 'qwen3:4b', mode: 'local', status: 'active' }

const mockFiles = [
  { file: 'Q4_Financial_Audit.pdf', modality: 'document', chunks: 24, ingested_at: '2026-11-05' },
  { file: 'Legal_Contract_Terms.docx', modality: 'document', chunks: 32, ingested_at: '2026-11-04' },
]

const conversationMessages = [
  {
    id: 'm1',
    role: 'user',
    text: 'What are the main liability clauses and audited revenue growth numbers in the Q4 filings?',
    timestamp: '2026-11-05T10:30:00Z',
  },
  {
    id: 'm2',
    role: 'assistant',
    usedLlm: true,
    text:
      'Based on the **Q4 Financial Audit** [1] and **Legal Contract Terms** [2], here is the verified breakdown:\n\n' +
      '### 1. Revenue & Margin Summary\n\n' +
      '| Metric | Q3 2024 | Q4 2024 | YoY Growth |\n' +
      '|---|---|---|---|\n' +
      '| **Enterprise Revenue** | $12.4M | **$14.8M** | +19.3% |\n' +
      '| **Gross Margin** | 71.2% | **73.5%** | +230 bps |\n' +
      '| **Operating Income** | $2.26M | **$3.17M** | +40.2% |\n\n' +
      '### 2. Statutory Liability & Compliance\n' +
      '- **Indemnification Cap**: Capped at **12 months of trailing aggregate fees** [2].\n' +
      '- **Data Sovereignty**: 100% on-premise offline hosting verified with zero egress calls [1].\n\n' +
      '```python\n' +
      '# Verified enterprise audit calculation\n' +
      'def compute_yoy_growth(prior: float, current: float) -> float:\n' +
      '    """Calculates year-over-year revenue expansion percentage."""\n' +
      '    return ((current - prior) / prior) * 100.0\n' +
      '```\n\n' +
      'All computations match the signed independent auditor assessment.',
    citations: [
      { index: 1, file: 'Q4_Financial_Audit.pdf', document: 'Q4_Financial_Audit.pdf', modality: 'document', page: 4, snippet: 'Fourth quarter enterprise revenue expanded to $14.8M, representing a 19.3% increase.' },
      { index: 2, file: 'Legal_Contract_Terms.docx', document: 'Legal_Contract_Terms.docx', modality: 'document', page: 12, snippet: 'Total aggregate liability under section 9.2 shall not exceed twelve months of fees.' },
    ],
    timestamp: '2026-11-05T10:30:04Z',
  },
]

const mockSessions = [
  { id: 's1', title: 'Contract Liability & Audit Review', created_at: '2026-11-05', updated_at: '2026-11-05', message_count: 8, file_count: 2 },
  { id: 's2', title: 'Cloud Infrastructure Migration Analysis', created_at: '2026-11-04', updated_at: '2026-11-04', message_count: 4, file_count: 1 },
]

async function setupScreenshotsMocks(page: Page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/api/auth/login' || path === '/api/auth/register') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ token: 'mock-jwt-token', user: regularUser }),
      })
      return
    }

    if (path === '/api/auth/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: regularUser }),
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
          index: { text_items: 88, image_items: 12 },
        }),
      })
      return
    }

    if (path === '/api/llm/active') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(localProvider),
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
            { name: 'ollama', label: 'Local Qwen (Ollama)', local: true, model: 'qwen3:4b', has_key: true, available: true, supports_images: true, supports_streaming: true },
            { name: 'gemini', label: 'Google Gemini', local: false, model: 'gemini-1.5-pro', has_key: true, available: true, supports_images: true, supports_streaming: true },
            { name: 'claude', label: 'Anthropic Claude 3.5 Sonnet', local: false, model: 'claude-3-5-sonnet', has_key: true, available: true, supports_images: true, supports_streaming: true },
          ],
        }),
      })
      return
    }

    if (path === '/api/files' || path === '/api/library') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ files: mockFiles, total: mockFiles.length }),
      })
      return
    }

    if (path === '/api/sessions') {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 's1',
            title: 'Contract Liability & Audit Review',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: 2,
            file_count: 2,
          }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sessions: mockSessions }),
      })
      return
    }

    if (path === '/api/sessions/s1') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 's1',
          title: 'Contract Liability & Audit Review',
          messages: conversationMessages,
          files: mockFiles,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      })
      return
    }

    if (path === '/api/transcribe') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          text: 'Compare the operating margins between third and fourth quarter from the audit report.',
          detected_language: 'en',
        }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
}

const artifactDir = 'C:\\Users\\HP\\.gemini\\antigravity\\brain\\689acc0c-4d09-42bd-a9f2-46a2f6d7a7c3'

test.describe('Stage 3 UI Screenshots', () => {
  test('Capture Stage 3 High-Fidelity Screenshots', async ({ page }) => {
    await setupScreenshotsMocks(page)

    // Set desktop viewport 1440x900
    await page.setViewportSize({ width: 1440, height: 900 })

    await page.goto('/')
    // Sign in
    await page.getByPlaceholder('you@example.com').fill(regularUser.email)
    await page.getByPlaceholder('Your password').fill('password123')
    await page.locator('form').getByRole('button', { name: 'Sign In' }).click()

    // Wait for Dashboard
    await expect(page.getByRole('heading', { name: 'Workspace Dashboard' })).toBeVisible()

    // Click "Start AI Chat" to open fresh empty chat
    await page.getByRole('button', { name: 'Start AI Chat' }).click()
    await expect(page.getByPlaceholder(/Ask a question in any language/i)).toBeVisible()
    await page.waitForTimeout(600)

    // 1. Empty chat state with prompt suggestion cards
    await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage3_empty_chat.png'), fullPage: false })

    // 2. Select existing session "Contract Liability & Audit Review" to view rich conversation
    await page.getByText('Contract Liability & Audit Review').first().click()
    await expect(page.getByText('Revenue & Margin Summary')).toBeVisible()
    await page.waitForTimeout(600)

    // 2. Active conversation with markdown tables, code block, citations, message actions
    await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage3_active_conversation.png'), fullPage: false })

    // 3. Close-up on long answer markdown table & code block
    await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage3_long_answer_markdown_table.png'), fullPage: false })

    // 4. Staged image with custom Hindi prompt
    await page.locator('input[data-testid="composer-image-input"]').setInputFiles({
      name: 'financial_breakdown_q4.png',
      mimeType: 'image/png',
      buffer: Buffer.from('mock-png-data'),
    })
    await page.waitForTimeout(300)
    const textarea = page.locator('textarea')
    await textarea.fill('इस चित्र में मौजूद डेटा को टेबल बनाकर समझाइए')
    await page.waitForTimeout(400)
    await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage3_image_staged_custom_prompt.png'), fullPage: false })

    // Clear staged image
    await page.getByTitle('Remove financial_breakdown_q4.png').click()
    await textarea.fill('')

    // 5. Staged audio with transcript review
    await page.locator('input[data-testid="composer-audio-input"]').setInputFiles({
      name: 'voice_memo_margins.mp3',
      mimeType: 'audio/mpeg',
      buffer: Buffer.from('mock-audio-data'),
    })
    await page.waitForTimeout(600)
    await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage3_audio_staged_transcript_review.png'), fullPage: false })

    // Clear staged audio
    await page.getByTitle('Remove voice_memo_margins.mp3').click()

    // 6. Model selector / provider panel screenshot
    await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage3_model_selector.png'), fullPage: false })

    // 7. Mobile chat view (390x844 iPhone 14)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.waitForTimeout(500)
    await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage3_mobile_chat.png'), fullPage: false })
  })
})
