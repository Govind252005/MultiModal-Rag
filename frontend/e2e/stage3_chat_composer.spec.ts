import { expect, test, type Page } from '@playwright/test'

const regularUser = { id: 'u1', email: 'analyst@enterprise.com', role: 'user', org_id: 'finance_dept' }
const localProvider = { provider: 'ollama', model: 'qwen3:4b', mode: 'local', status: 'active' }

const mockFiles = [
  { file: 'Q4_Financial_Audit.pdf', modality: 'document', chunks: 24, ingested_at: '2026-11-05' },
]

async function setupStage3Mocks(page: Page) {
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
          index: { text_items: 42, image_items: 8 },
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
            id: 'sess-new',
            title: 'New Analysis',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: 0,
            file_count: 0,
          }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sessions: [] }),
      })
      return
    }

    if (path === '/api/sessions/sess-new') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'sess-new',
          title: 'New Analysis',
          messages: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      })
      return
    }

    if (path === '/api/query/stream') {
      const sseBody = [
        'event: citations\ndata: [{"index":1,"document":"Q4_Financial_Audit.pdf","page":4,"snippet":"Fourth quarter revenue reached $14.8M, representing a 19.3% increase over Q3."}]\n\n',
        'event: delta\ndata: {"text":"Based on the audited records [1], here is the financial summary:\\n\\n"}\n\n',
        'event: delta\ndata: {"text":"| Metric | Q3 2024 | Q4 2024 |\\n|---|---|---|\\n| Revenue | $12.4M | $14.8M |\\n| Net Margin | 18.2% | 21.4% |\\n\\n"}\n\n',
        'event: delta\ndata: {"text":"```python\\n# Audit validation code\\ndef verify_revenue(q3, q4):\\n    return (q4 - q3) / q3\\n```\\n\\n"}\n\n',
        'event: done\ndata: {"used_llm":true,"metrics":{}}\n\n',
      ].join('')

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseBody,
      })
      return
    }

    if (path === '/api/query/image' || path === '/api/query-image') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'इस चित्र में मौजूद वित्तीय तालिका के अनुसार राजस्व $14.8M दर्ज हुआ है।',
          citations: [
            { index: 1, document: 'Uploaded: test_chart.png', score: 0.98, snippet: 'OCR: Q4 Revenue $14.8M' },
          ],
          query_caption: 'A bar chart showing quarterly financial performance',
          query_ocr: 'Q4 Revenue $14.8M Net Margin 21.4%',
          used_llm: true,
          session_id: 'sess-new',
        }),
      })
      return
    }

    if (path === '/api/transcribe') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          text: 'Explain the third quarter revenue trends from the audit report.',
          detected_language: 'en',
        }),
      })
      return
    }

    if (path === '/api/query/audio' || path === '/api/query-audio') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'Here is the analysis of third quarter revenue trends from your spoken request.',
          citations: [
            { index: 1, document: 'Q4_Financial_Audit.pdf', score: 0.92, snippet: 'Q3 revenue trends analysis' },
          ],
          transcript: 'Explain the third quarter revenue trends from the audit report.',
          used_llm: true,
          session_id: 'sess-new',
        }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
}

async function navigateToChat(page: Page) {
  await page.goto('/')
  // Sign in
  await page.getByPlaceholder('you@example.com').fill(regularUser.email)
  await page.getByPlaceholder('Your password').fill('password123')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()

  // Wait for Dashboard
  await expect(page.getByRole('heading', { name: 'Workspace Dashboard' })).toBeVisible()

  // Click "Start AI Chat"
  await page.getByRole('button', { name: 'Start AI Chat' }).click()

  // Wait for Chat view
  await expect(page.getByPlaceholder(/Ask a question in any language/i)).toBeVisible()
}

test.describe('Stage 3 — Premium Chat Interface & Unified Staged Composer', () => {
  test('TC-STG3-01: Chat view renders empty state with prompt suggestions', async ({ page }) => {
    await setupStage3Mocks(page)
    await navigateToChat(page)

    // Verify empty state header and subtitle
    await expect(page.getByText('Enterprise Multimodal Chat')).toBeVisible()
    await expect(page.getByText('Ask questions in any language')).toBeVisible()

    // Check prompt suggestion cards exist
    await expect(page.getByText('Analyze Financial Summary')).toBeVisible()
    await expect(page.getByText('Document Intelligence')).toBeVisible()
    await expect(page.getByText('Multimodal Image Query')).toBeVisible()
    await expect(page.getByText('Audio Meeting Review')).toBeVisible()

    // Composer textarea is ready
    const composer = page.getByPlaceholder(/Ask a question in any language/i)
    await expect(composer).toBeVisible()
  })

  test('TC-STG3-02: Text query streams response with Markdown, HTML Table, Code Block, and Citation pill', async ({ page }) => {
    await setupStage3Mocks(page)
    await navigateToChat(page)

    const composer = page.getByPlaceholder(/Ask a question in any language/i)
    await composer.fill('What is the Q4 revenue summary?')
    await page.getByTitle('Send message (Enter)').click()

    // Verify user message appears in chat
    await expect(page.getByText('What is the Q4 revenue summary?')).toBeVisible()

    // Verify streaming table content renders cleanly
    await expect(page.getByText('$14.8M').first()).toBeVisible()
    await expect(page.getByText('Net Margin').first()).toBeVisible()

    // Verify code block rendered with language header and copy button
    await expect(page.getByText('python')).toBeVisible()
    await expect(page.getByText('# Audit validation code')).toBeVisible()

    // Verify citation pill [1] is rendered (with title 'View supporting evidence source [1]')
    await expect(page.getByTitle('View supporting evidence source [1]').first()).toBeVisible()

    // Verify message actions (Copy, Regenerate, Thumbs)
    await expect(page.getByTitle('Copy answer to clipboard')).toBeVisible()
    await expect(page.getByTitle('Regenerate answer')).toBeVisible()
  })

  test('TC-STG3-03: Image attachment staging with thumbnail preview and dismiss (X)', async ({ page }) => {
    await setupStage3Mocks(page)
    await navigateToChat(page)

    // Stage an image file via the hidden image input directly
    await page.locator('input[data-testid="composer-image-input"]').setInputFiles({
      name: 'test_chart.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image-png-bytes'),
    })

    // Staging card should be visible with file name and image type tag
    await expect(page.getByText('test_chart.png')).toBeVisible()
    await expect(page.getByText(/image/i).first()).toBeVisible()

    // Staging card has dismiss button
    const dismissBtn = page.getByTitle('Remove test_chart.png')
    await expect(dismissBtn).toBeVisible()
    await dismissBtn.click()

    // Should no longer be staged
    await expect(page.getByText('test_chart.png')).not.toBeVisible()
  })

  test('TC-STG3-04: Image attachment with custom prompt input (Devanagari query) and explicit Send', async ({ page }) => {
    await setupStage3Mocks(page)
    await navigateToChat(page)

    // Stage an image file
    await page.locator('input[data-testid="composer-image-input"]').setInputFiles({
      name: 'test_chart.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image-png-bytes'),
    })

    // Verify staged
    await expect(page.getByText('test_chart.png')).toBeVisible()

    // Type a custom Hindi question
    const composer = page.getByPlaceholder(/Enter custom question or instruction/i)
    const customPrompt = 'इस चित्र में मौजूद डेटा को टेबल बनाकर समझाइए'
    await composer.fill(customPrompt)

    // Click explicit Send
    await page.getByTitle('Send message (Enter)').click()

    // User message should display the custom prompt and image attachment
    await expect(page.getByText(customPrompt)).toBeVisible()
    await expect(page.locator('img[alt="User attachment"]')).toBeVisible()

    // Assistant response should appear
    await expect(page.getByText('इस चित्र में मौजूद वित्तीय तालिका के अनुसार राजस्व $14.8M दर्ज हुआ है।')).toBeVisible()
  })

  test('TC-STG3-05: Audio attachment stages player, triggers transcription preview, and supports explicit Send', async ({ page }) => {
    await setupStage3Mocks(page)
    await navigateToChat(page)

    // Stage an audio file
    await page.locator('input[data-testid="composer-audio-input"]').setInputFiles({
      name: 'meeting_notes.mp3',
      mimeType: 'audio/mpeg',
      buffer: Buffer.from('fake-audio-bytes'),
    })

    // Wait for staged card and transcript review preview
    await expect(page.getByText('meeting_notes.mp3')).toBeVisible()
    await expect(page.getByText('Explain the third quarter revenue trends from the audit report.')).toBeVisible()

    // Click explicit Send
    await page.getByTitle('Send message (Enter)').click()

    // Assistant response appears
    await expect(page.getByText('Here is the analysis of third quarter revenue trends from your spoken request.')).toBeVisible()
  })
})
