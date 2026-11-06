import { test, expect } from '@playwright/test'

const adminUser = {
  id: 'admin_1',
  email: 'admin@enterprise.org',
  role: 'admin',
  org_id: 'enterprise_hq',
}

const mockDocuments = [
  {
    filename: 'Global_Compliance_Handbook_2025.pdf',
    modality: 'pdf',
    size_bytes: 3450200,
    page_count: 42,
    chunk_count: 88,
    status: 'indexed',
    created_at: '2026-11-06T08:00:00Z',
    collections: ['Compliance & Audit', 'Legal Dept'],
    session_id: 'sess_admin_01',
  },
  {
    filename: 'Master_Services_Agreement_Q4.docx',
    modality: 'docx',
    size_bytes: 842100,
    page_count: 0,
    chunk_count: 24,
    status: 'indexed',
    created_at: '2026-11-05T14:30:00Z',
    collections: ['Contracts 2025'],
    session_id: 'sess_admin_01',
  },
  {
    filename: 'Server_Rack_Topology_Diagram.png',
    modality: 'image',
    size_bytes: 1245000,
    page_count: 0,
    chunk_count: 4,
    status: 'indexed',
    created_at: '2026-11-04T10:15:00Z',
    collections: ['Infrastructure'],
    session_id: 'sess_admin_01',
  },
  {
    filename: 'Quarterly_Earnings_Call_Transcript.mp3',
    modality: 'audio',
    size_bytes: 6520000,
    page_count: 0,
    chunk_count: 19,
    status: 'indexed',
    created_at: '2026-11-03T09:00:00Z',
    collections: ['Executive'],
    session_id: 'sess_admin_01',
  },
]

const mockCollections = [
  {
    id: 'col_legal_01',
    name: 'Compliance & Audit',
    description: 'Strict regulatory and GDPR compliance documentation for enterprise audits.',
    owner_id: 'admin_1',
    org_id: 'enterprise_hq',
    files: ['Global_Compliance_Handbook_2025.pdf'],
    file_count: 1,
    is_shared: true,
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-06T08:00:00Z',
  },
  {
    id: 'col_contracts_02',
    name: 'Contracts 2025',
    description: 'Active commercial agreements and NDA agreements.',
    owner_id: 'admin_1',
    org_id: 'enterprise_hq',
    files: ['Master_Services_Agreement_Q4.docx'],
    file_count: 1,
    is_shared: true,
    created_at: '2026-11-02T11:00:00Z',
    updated_at: '2026-11-05T14:30:00Z',
  },
]

const mockOllamaStatus = {
  status: 'ok',
  is_online: true,
  latency_ms: 12,
  default_model: 'qwen3:4b',
  models: [
    { name: 'qwen3:4b', size: 2576980377, modified_at: '2026-11-06T05:00:00Z' },
    { name: 'llama3:8b', size: 4920721408, modified_at: '2026-11-05T08:00:00Z' },
  ],
}

const mockEmbeddingMeta = {
  dense_model: 'BAAI/bge-m3',
  dense_dimension: 1024,
  clip_model: 'openai/clip-vit-base-patch32',
  clip_dimension: 512,
}

const mockUsers = [
  {
    id: 'u_1',
    email: 'admin@enterprise.org',
    role: 'admin',
    org_id: 'enterprise_hq',
    status: 'active',
    created_at: '2026-10-01T08:00:00Z',
  },
  {
    id: 'u_2',
    email: 'analyst@enterprise.org',
    role: 'user',
    org_id: 'enterprise_hq',
    status: 'active',
    created_at: '2026-10-15T09:30:00Z',
  },
  {
    id: 'u_3',
    email: 'contractor@thirdparty.com',
    role: 'user',
    org_id: 'enterprise_hq',
    status: 'disabled',
    created_at: '2026-11-01T12:00:00Z',
  },
]

const mockAuditLogs = [
  {
    id: 'log_01',
    timestamp: '2026-11-06T09:15:32Z',
    action: 'query',
    user_email: 'analyst@enterprise.org',
    user_id: 'u_2',
    org_id: 'enterprise_hq',
    details: { collection_id: 'col_legal_01', query: 'What is the GDPR retention period?' },
    ip: '192.168.1.45',
  },
  {
    id: 'log_02',
    timestamp: '2026-11-06T08:12:10Z',
    action: 'document_upload',
    user_email: 'admin@enterprise.org',
    user_id: 'u_1',
    org_id: 'enterprise_hq',
    details: { filename: 'Global_Compliance_Handbook_2025.pdf', chunks: 88 },
    ip: '127.0.0.1',
  },
  {
    id: 'log_03',
    timestamp: '2026-11-05T16:40:11Z',
    action: 'account_disabled',
    user_email: 'admin@enterprise.org',
    user_id: 'u_1',
    org_id: 'enterprise_hq',
    details: { target_email: 'contractor@thirdparty.com' },
    ip: '127.0.0.1',
  },
]

test.describe('Stage 5 — Enterprise Management & Administration', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'mock_jwt_token_admin')
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'admin_1',
          email: 'admin@enterprise.org',
          role: 'admin',
          org_id: 'enterprise_hq',
        })
      )
    })

    await page.route('**/api/**', async (route) => {
      const url = new URL(route.request().url())
      const path = url.pathname

      if (path === '/api/auth/me') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ user: adminUser }),
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
            llm_model: 'qwen3:4b',
            llm_available: true,
            ocr_engine: 'tesseract',
            index: { total_documents: 135, dense_model: 'BAAI/bge-m3' },
            default_provider: 'ollama',
          }),
        })
        return
      }

      if (path === '/api/sessions') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ sessions: [] }),
        })
        return
      }

      if (path.startsWith('/api/files')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ files: [] }),
        })
        return
      }

      if (path === '/api/llm/providers/active' || path === '/api/llm/active') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            provider: 'ollama',
            model: 'qwen3:4b',
            mode: 'local',
            is_local: true,
            status: 'active',
          }),
        })
        return
      }

      if (path === '/api/providers' || path === '/api/llm/providers') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            providers: [
              { name: 'ollama', label: 'Local Ollama', local: true, model: 'qwen3:4b', has_key: true, available: true, supports_images: true, supports_streaming: true },
              { name: 'gemini', label: 'Google Gemini', local: false, model: 'gemini-1.5-pro', has_key: false, available: true, supports_images: true, supports_streaming: true },
            ],
            default: 'ollama',
          }),
        })
        return
      }

      if (path === '/api/documents') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ documents: mockDocuments, total: mockDocuments.length }),
        })
        return
      }

      if (path === '/api/collections') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ collections: mockCollections, total: mockCollections.length }),
        })
        return
      }

      if (path === '/api/models/ollama/status') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockOllamaStatus),
        })
        return
      }

      if (path === '/api/models/embedding') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockEmbeddingMeta),
        })
        return
      }

      if (path === '/api/admin/users') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ users: mockUsers }),
        })
        return
      }

      if (path === '/api/admin/audit-logs') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ logs: mockAuditLogs, total: mockAuditLogs.length }),
        })
        return
      }

      if (path === '/api/documents/upload') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ status: 'ok', filename: 'Uploaded_Sample.pdf' }),
        })
        return
      }

      await route.fallback()
    })
  })

  test('renders Document Library with filtering, search, and view switcher', async ({ page }) => {
    await page.goto('/')

    // Navigate to Documents view
    await page.getByRole('button', { name: 'Documents', exact: true }).click()

    // Heading verification
    await expect(page.getByRole('heading', { name: /Enterprise Document Library/i })).toBeVisible()
    await expect(page.getByText('Global_Compliance_Handbook_2025.pdf')).toBeVisible()
    await expect(page.getByText('Master_Services_Agreement_Q4.docx')).toBeVisible()
    await expect(page.getByText('Server_Rack_Topology_Diagram.png')).toBeVisible()

    // Test Search input
    const searchInput = page.getByPlaceholder(/Search documents by filename/i)
    await searchInput.fill('Compliance')
    await expect(page.getByText('Global_Compliance_Handbook_2025.pdf')).toBeVisible()
    await expect(page.getByText('Master_Services_Agreement_Q4.docx')).not.toBeVisible()

    await searchInput.clear()

    // Switch to Grid View
    await page.getByTitle('Grid view').click()
    await expect(page.getByText('88 chunks')).toBeVisible()

    // Switch back to Table View
    await page.getByTitle('Table view').click()
    await expect(page.getByRole('table')).toBeVisible()
  })

  test('supports Document Ingestion Modal with multi-stage progress', async ({ page }) => {
    await page.goto('/')

    await page.getByRole('button', { name: 'Documents', exact: true }).click()

    // Open upload modal
    await page.getByRole('button', { name: 'Upload Document' }).click()
    await expect(page.getByRole('heading', { name: /Upload & Ingest Enterprise Documents/i })).toBeVisible()

    // Select collection dropdown should exist
    await expect(page.getByLabel(/Assign to Collection/i)).toBeVisible()
    await expect(page.getByText(/Drop file here or click to browse/i)).toBeVisible()

    // Cancel modal
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('heading', { name: /Upload & Ingest Enterprise Documents/i })).not.toBeVisible()
  })

  test('renders Collections Dashboard and opens Collection Detail Drawer', async ({ page }) => {
    await page.goto('/')

    // Navigate to Collections view
    await page.getByRole('button', { name: 'Collections', exact: true }).click()

    await expect(page.getByRole('heading', { name: /Document Collections & Isolation/i })).toBeVisible()
    await expect(page.getByText('Compliance & Audit')).toBeVisible()
    await expect(page.getByText('Contracts 2025')).toBeVisible()

    // Open Collection Detail Drawer by clicking card
    await page.getByText('Compliance & Audit').first().click()
    await expect(page.getByText('Active Collection Scope')).toBeVisible()
    await expect(page.getByText('Strict Scope Enforced')).toBeVisible()
    await expect(page.getByText('Global_Compliance_Handbook_2025.pdf')).toBeVisible()

    // Test Scoped Chat action
    await page.getByRole('button', { name: /Start Scoped Chat/i }).click()

    // Should switch to Chat view with collection badge visible
    await expect(page.getByText(/Collection: Compliance & Audit/i)).toBeVisible()
  })

  test('renders Model Settings with Ollama probe and Privacy Transparency Matrix', async ({ page }) => {
    await page.goto('/')

    // Navigate to Settings
    await page.getByRole('button', { name: 'Models & Settings', exact: true }).click()

    await expect(page.getByRole('heading', { name: /Model Settings & Local AI Telemetry/i })).toBeVisible()

    // Check Ollama status card
    await expect(page.getByText(/Ollama Local LLM Engine/i)).toBeVisible()
    await expect(page.getByText('12 ms')).toBeVisible()
    await expect(page.getByText('qwen3:4b').first()).toBeVisible()

    // Check Vector & Embedding Stack
    await expect(page.getByText(/BAAI\/bge-m3/i)).toBeVisible()
    await expect(page.getByText('1024-dimensional')).toBeVisible()
    await expect(page.getByText('512-dimensional')).toBeVisible()

    // Check Privacy Transparency Matrix
    await expect(page.getByText(/Enterprise Privacy & Data Egress Transparency Matrix/i)).toBeVisible()
    await expect(page.getByText(/Zero cloud egress \(Local GPU\/CPU\)/i)).toBeVisible()
    await expect(page.getByText(/Streams audio to Browser Vendor \(Google\/Apple\)/i)).toBeVisible()
  })

  test('renders Administration Console with RBAC user management and Audit Logs', async ({ page }) => {
    await page.goto('/')

    // Navigate to Admin
    await page.getByRole('button', { name: 'Administration', exact: true }).click()

    await expect(page.getByRole('heading', { name: /Enterprise Administration/i })).toBeVisible()

    // User management tab
    await expect(page.getByRole('cell', { name: 'admin@enterprise.org' })).toBeVisible()
    await expect(page.getByText('contractor@thirdparty.com')).toBeVisible()
    await expect(page.getByText('Disabled').first()).toBeVisible()

    // Switch to Audit Logs tab
    await page.getByRole('button', { name: /Security Audit Logs/i }).click()
    await expect(page.getByText('query').first()).toBeVisible()
    await expect(page.getByText('document_upload').first()).toBeVisible()
    await expect(page.getByText('account_disabled').first()).toBeVisible()

    // Inspect audit event
    await page.getByRole('button', { name: 'Inspect' }).first().click()
    await expect(page.getByRole('heading', { name: /Audit Log Event Inspection/i })).toBeVisible()
    await page.getByRole('button', { name: 'Close', exact: true }).click()
  })

  test('tablet viewport (768px) and mobile viewport (390px) responsive enterprise navigation', async ({ page }) => {
    // 768px Tablet
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('/')

    await page.getByLabel('Open navigation menu').click()
    await page.getByRole('button', { name: 'Documents', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Enterprise Document Library/i })).toBeVisible()

    await page.getByLabel('Open navigation menu').click()
    await page.getByRole('button', { name: 'Collections', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Document Collections & Isolation/i })).toBeVisible()

    // 390px Mobile
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')

    await page.getByLabel('Open navigation menu').click()
    await page.getByRole('button', { name: 'Administration', exact: true }).click()
    await expect(page.getByRole('heading', { name: /Enterprise Administration/i })).toBeVisible()
  })
})
