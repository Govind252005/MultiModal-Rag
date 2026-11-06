import { test, expect } from '@playwright/test'
import path from 'path'

const ARTIFACT_DIR = 'C:/Users/HP/.gemini/antigravity/brain/689acc0c-4d09-42bd-a9f2-46a2f6d7a7c3'

const testAdmin = {
  id: 'qa_admin_id',
  email: 'admin@enterprise.org',
  role: 'admin',
  org_id: 'enterprise_hq',
}

const mockSessions = [
  {
    id: 'sess_stage6_01',
    title: 'Rylands v Fletcher Liability Audit',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    message_count: 2,
  },
]

const mockSessionDetail = {
  id: 'sess_stage6_01',
  name: 'Rylands v Fletcher Liability Audit',
  created_at: '2026-11-06T09:00:00Z',
  messages: [
    { id: 'm1', role: 'user', text: 'What were the material facts and rule established in Rylands v Fletcher?' },
    {
      id: 'm2',
      role: 'assistant',
      text: 'In the landmark case of Rylands v Fletcher [1], the defendant employed contractors who failed to exercise reasonable care [2]. Under strict liability principles [3], strict liability applies to hazardous materials storage without proof of negligence. In Hindi legal analysis [4], उचित सावधानी और कौशल का अभाव स्पष्ट रूप से रेखांकित किया गया है।',
      citations: [
        { index: 1, file: 'Rylands_v_Fletcher_1868.pdf', page: 1, snippet: 'The shafts were vertical, the passages horizontal, and the former especially seemed filled with marl and rubbish.' },
        { index: 2, file: 'Rylands_v_Fletcher_1868.pdf', page: 3, snippet: 'reasonable and proper care and skill were not exercised by, or on the part of, the persons so employed by them' },
        { index: 3, file: 'Global_Compliance_Handbook.docx', snippet: 'Section 4: Strict liability applies to hazardous materials storage without proof of negligence.' },
        { index: 4, file: 'Hindi_Legal_Notice_अनुबंध.pdf', page: 2, snippet: 'प्रतिवादी ने निर्माण कार्य के दौरान उचित सावधानी और कौशल का प्रयोग नहीं किया' },
      ],
      usedLlm: true,
    },
  ],
}

const mockDocuments = [
  {
    filename: 'Rylands_v_Fletcher_1868.pdf',
    modality: 'pdf',
    size_bytes: 2450000,
    page_count: 5,
    chunk_count: 12,
    status: 'indexed',
    created_at: '2026-11-05T10:00:00Z',
    collections: ['Legal Vault'],
    session_id: 'sess_stage6_01',
  },
  {
    filename: 'Global_Compliance_Handbook.docx',
    modality: 'docx',
    size_bytes: 920000,
    page_count: 0,
    chunk_count: 18,
    status: 'indexed',
    created_at: '2026-11-05T11:00:00Z',
    collections: ['Compliance & Safety'],
    session_id: 'sess_stage6_01',
  },
  {
    filename: 'Hindi_Legal_Notice_अनुबंध.pdf',
    modality: 'pdf',
    size_bytes: 1840000,
    page_count: 4,
    chunk_count: 8,
    status: 'indexed',
    created_at: '2026-11-05T12:00:00Z',
    collections: ['Multilingual Archives'],
    session_id: 'sess_stage6_01',
  },
]

const mockCollections = [
  {
    id: 'col_legal_vault',
    name: 'Legal Vault',
    description: 'Case law precedents and appellate court rulings.',
    owner_id: 'qa_admin_id',
    org_id: 'enterprise_hq',
    files: ['Rylands_v_Fletcher_1868.pdf'],
    file_count: 1,
    is_shared: true,
    created_at: '2026-11-01T08:00:00Z',
    updated_at: '2026-11-06T09:00:00Z',
  },
  {
    id: 'col_multilingual',
    name: 'Multilingual Archives',
    description: 'Devanagari, Hindi, and cross-lingual international contracts.',
    owner_id: 'qa_admin_id',
    org_id: 'enterprise_hq',
    files: ['Hindi_Legal_Notice_अनुबंध.pdf'],
    file_count: 1,
    is_shared: true,
    created_at: '2026-11-02T10:00:00Z',
    updated_at: '2026-11-06T09:00:00Z',
  },
]

const mockUsers = [
  {
    id: 'qa_admin_id',
    email: 'admin@enterprise.org',
    role: 'admin',
    org_id: 'enterprise_hq',
    status: 'active',
    created_at: '2026-11-01T08:00:00Z',
  },
  {
    id: 'user_analyst_2',
    email: 'analyst@enterprise.org',
    role: 'user',
    org_id: 'enterprise_hq',
    status: 'active',
    created_at: '2026-11-03T11:00:00Z',
  },
]

const mockAuditLogs = [
  {
    id: 'audit_01',
    timestamp: '2026-11-06T09:15:00Z',
    action: 'document_uploaded',
    user_id: 'qa_admin_id',
    user_email: 'admin@enterprise.org',
    org_id: 'enterprise_hq',
    resource: 'Hindi_Legal_Notice_अनुबंध.pdf',
    outcome: 'success',
    ip: '127.0.0.1',
    details: { chunks: 8, collection: 'Multilingual Archives' },
  },
  {
    id: 'audit_02',
    timestamp: '2026-11-06T09:20:00Z',
    action: 'cross_lingual_retrieval',
    user_id: 'qa_admin_id',
    user_email: 'admin@enterprise.org',
    org_id: 'enterprise_hq',
    resource: 'Rylands v Fletcher Liability Audit',
    outcome: 'success',
    ip: '127.0.0.1',
    details: { query_script: 'Devanagari', dense_mrr: 0.85 },
  },
]

async function setupMockRoutes(page: any, authenticated = true) {
  if (authenticated) {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'fake_qa_admin_token')
      localStorage.setItem('user', JSON.stringify(testAdmin))
    })
  } else {
    await page.addInitScript(() => {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    })
  }

  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/api/auth/me') {
      if (!authenticated) return route.fulfill({ status: 401, json: { detail: 'Not authenticated' } })
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user: testAdmin }) })
    }

    if (path === '/api/health') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ok',
          llm_available: true,
          provider: 'ollama',
          device: 'cuda',
          models_available: 50,
          document_count: 50,
          total_chunks: 180,
          collection_count: 8,
          active_model: 'qwen3:4b',
          default_provider: 'ollama',
          index: { total_documents: 50, dense_model: 'BAAI/bge-m3' },
        }),
      })
    }

    if (path === '/api/sessions') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ sessions: mockSessions }) })
    }

    if (path === '/api/sessions/sess_stage6_01') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockSessionDetail) })
    }

    if (path.startsWith('/api/files')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ files: [] }) })
    }

    if (path === '/api/llm/providers/active' || path === '/api/llm/active' || path === '/api/active-provider') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ provider: 'ollama', model: 'qwen3:4b', mode: 'local', is_local: true, status: 'active' }),
      })
    }

    if (path === '/api/providers' || path === '/api/llm/providers') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          providers: [{ name: 'ollama', label: 'Local Ollama', local: true, model: 'qwen3:4b', has_key: true, available: true }],
          default: 'ollama',
        }),
      })
    }

    if (path === '/api/documents') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ documents: mockDocuments, total: mockDocuments.length }) })
    }

    if (path === '/api/collections') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ collections: mockCollections, total: mockCollections.length }) })
    }

    if (path === '/api/admin/users') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ users: mockUsers, total: mockUsers.length }) })
    }

    if (path === '/api/admin/audit-logs') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ logs: mockAuditLogs, total: mockAuditLogs.length, events: mockAuditLogs }) })
    }

    if (path === '/api/models/ollama/status') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          installed: true,
          running: true,
          version: '0.4.1',
          endpoint: 'http://localhost:11434',
          active_model: 'qwen3:4b',
          models: [{ name: 'qwen3:4b', size: 2500000000, modified_at: '2026-11-05T08:00:00Z' }],
        }),
      })
    }

    if (path === '/api/models/embedding') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          model_name: 'BAAI/bge-m3',
          dense_model: 'BAAI/bge-m3',
          dimensions: 1024,
          dense_dimension: 1024,
          multilingual: true,
          supported_languages: ['English', 'Hindi', 'Hinglish', 'Spanish', 'French', 'German', 'Arabic'],
          device: 'cuda',
          clip_model: 'ViT-B/32',
          clip_dimension: 512,
        }),
      })
    }

    if (path.includes('/content')) {
      if (path.includes('Hindi')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            filename: 'Hindi_Legal_Notice_अनुबंध.pdf',
            modality: 'pdf',
            page_count: 4,
            current_page: 2,
            pages: [
              { page_number: 1, text: 'न्यायालयीन सूचना एवं विधिक विश्लेषण।' },
              { page_number: 2, text: 'प्रतिवादी ने निर्माण कार्य के दौरान उचित सावधानी और कौशल का प्रयोग नहीं किया और भारी क्षति कारित हुई।' },
              { page_number: 3, text: 'दायित्व का निर्धारण स्पष्ट साक्ष्यों के आधार पर किया गया है।' },
              { page_number: 4, text: 'समापन एवं विधिक निर्देश।' },
            ],
          }),
        })
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          filename: 'Global_Compliance_Handbook.docx',
          modality: 'docx',
          text_content: 'GLOBAL COMPLIANCE HANDBOOK (2025)\n\nChapter 1: Environmental and Safety Guidelines\n\nSection 4: Strict liability applies to hazardous materials storage without proof of negligence.\n\nAll facility managers must maintain automated leak detection systems.',
        }),
      })
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) })
  })
}

test.describe('Stage 6 Real Visual Artifact Capture Suite', () => {

  test('Capture 1: Landing Page', async ({ page }) => {
    await setupMockRoutes(page, false)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await expect(page.getByText('Multimodal RAG')).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_01_landing_page.png') })
  })

  test('Capture 2: Authenticated Dashboard', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Workspace Dashboard' })).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_02_dashboard.png') })
  })

  test('Capture 3: AI Chat with Streamed Response', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    const sessionCard = page.locator('text=Rylands v Fletcher Liability Audit').first()
    await sessionCard.click()
    await expect(page.getByText('Rylands v Fletcher Liability Audit')).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_03_ai_chat_streamed.png') })
  })

  test('Capture 4: Evidence Viewer with Verified Citation Highlighting (DOCX)', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    const sessionCard = page.locator('text=Rylands v Fletcher Liability Audit').first()
    await sessionCard.click()
    const citBtn = page.locator('button[title*="source [3]"]').first()
    await citBtn.click()
    await expect(page.getByRole('heading', { name: 'Global_Compliance_Handbook.' })).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_04_evidence_viewer_highlighted.png') })
  })

  test('Capture 5: Hindi / Devanagari Evidence Verification', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    const sessionCard = page.locator('text=Rylands v Fletcher Liability Audit').first()
    await sessionCard.click()
    const citBtn = page.locator('button[title*="source [4]"]').first()
    await citBtn.click()
    await expect(page.getByRole('heading', { name: 'Hindi_Legal_Notice_अनुबंध.pdf' })).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_05_hindi_devanagari_evidence.png') })
  })

  test('Capture 6: Document Management (Enterprise Vault)', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Documents', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Enterprise Document Library/i })).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_06_document_management.png') })
  })

  test('Capture 7: Collection Management', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Collections', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Document Collections & Isolation/i })).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_07_collection_management.png') })
  })

  test('Capture 8: Model Settings & Offline Guarantees', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Models & Settings', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Model Settings & Local AI Telemetry/i })).toBeVisible()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_08_model_settings.png') })
  })

  test('Capture 9: Enterprise Administration & Audit Logs', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Administration', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Enterprise Administration/i })).toBeVisible()
    const auditTab = page.getByRole('button', { name: /Audit Logs/i })
    await auditTab.click()
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_09_enterprise_administration.png') })
  })

  test('Capture 10: Accessibility & Keyboard Navigation Focus State', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Documents', exact: true }).click()
    const search = page.getByPlaceholder(/Search documents by filename/i)
    await search.focus()
    await page.keyboard.press('Tab')
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_10_accessibility_keyboard_nav.png') })
  })

  test('Capture 11: Desktop Layout (1440x900)', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_11_desktop_1440x900.png') })
  })

  test('Capture 12: Tablet Layout (768x1024)', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('/')
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_12_tablet_768x1024.png') })
  })

  test('Capture 13: Mobile Layout (390x844)', async ({ page }) => {
    await setupMockRoutes(page, true)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')
    await page.screenshot({ path: path.join(ARTIFACT_DIR, 'screenshot_stage6_13_mobile_390x844.png') })
  })

})
