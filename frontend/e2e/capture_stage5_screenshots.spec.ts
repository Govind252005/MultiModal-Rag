import { test } from '@playwright/test'
import path from 'path'

const artifactDir = 'C:\\Users\\HP\\.gemini\\antigravity\\brain\\689acc0c-4d09-42bd-a9f2-46a2f6d7a7c3'

const adminUser = {
  id: 'admin_1',
  email: 'legal.admin@enterprise.org',
  role: 'admin',
  org_id: 'enterprise_legal',
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
    org_id: 'enterprise_legal',
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
    org_id: 'enterprise_legal',
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
    email: 'legal.admin@enterprise.org',
    role: 'admin',
    org_id: 'enterprise_legal',
    status: 'active',
    created_at: '2026-10-01T08:00:00Z',
  },
  {
    id: 'u_2',
    email: 'compliance.officer@enterprise.org',
    role: 'user',
    org_id: 'enterprise_legal',
    status: 'active',
    created_at: '2026-10-15T09:30:00Z',
  },
  {
    id: 'u_3',
    email: 'external.auditor@consulting.com',
    role: 'user',
    org_id: 'enterprise_legal',
    status: 'disabled',
    created_at: '2026-11-01T12:00:00Z',
  },
]

const mockAuditLogs = [
  {
    id: 'log_01',
    timestamp: '2026-11-06T09:15:32Z',
    action: 'query',
    user_email: 'compliance.officer@enterprise.org',
    user_id: 'u_2',
    org_id: 'enterprise_legal',
    details: { collection_id: 'col_legal_01', query: 'What is the GDPR data retention rule?' },
    ip: '192.168.1.45',
  },
  {
    id: 'log_02',
    timestamp: '2026-11-06T08:12:10Z',
    action: 'document_upload',
    user_email: 'legal.admin@enterprise.org',
    user_id: 'u_1',
    org_id: 'enterprise_legal',
    details: { filename: 'Global_Compliance_Handbook_2025.pdf', chunks: 88 },
    ip: '127.0.0.1',
  },
  {
    id: 'log_03',
    timestamp: '2026-11-05T16:40:11Z',
    action: 'account_disabled',
    user_email: 'legal.admin@enterprise.org',
    user_id: 'u_1',
    org_id: 'enterprise_legal',
    details: { target_email: 'external.auditor@consulting.com' },
    ip: '127.0.0.1',
  },
]

test('Capture Stage 5 Enterprise Visual Verification Screenshots', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'mock_jwt_token_admin')
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 'admin_1',
        email: 'legal.admin@enterprise.org',
        role: 'admin',
        org_id: 'enterprise_legal',
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

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')

  // 1. Documents Table View
  await page.getByRole('button', { name: 'Documents', exact: true }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_document_library_table.png') })

  // 2. Documents Grid View
  await page.getByTitle('Grid view').click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_document_library_grid.png') })

  // 3. Document Ingestion Modal with Pipeline Stages
  await page.getByRole('button', { name: 'Upload Document' }).click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_upload_modal_stages.png') })
  await page.getByRole('button', { name: 'Cancel' }).click()

  // 4. Collections Dashboard
  await page.getByRole('button', { name: 'Collections', exact: true }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_collections_dashboard.png') })

  // 5. Collection Detail Drawer
  await page.getByText('Compliance & Audit').first().click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_collection_detail_drawer.png') })

  // 6. Create Collection Modal
  await page.getByRole('button', { name: 'New Collection' }).click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_create_collection_modal.png') })
  await page.getByRole('button', { name: 'Cancel' }).click()

  // 7. Collection Scoped Chat
  await page.getByRole('button', { name: /Start Scoped Chat/i }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_collection_scoped_chat.png') })

  // 8. Model Settings View (Ollama status & Vector engine)
  await page.getByRole('button', { name: 'Models & Settings', exact: true }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_model_settings_ollama.png') })

  // 9. Privacy Transparency Matrix
  const privacySection = page.getByText(/Enterprise Privacy & Data Egress Transparency Matrix/i).locator('..').locator('..')
  await privacySection.scrollIntoViewIfNeeded()
  await page.waitForTimeout(300)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_privacy_offline_matrix.png') })

  // 10. Admin RBAC Users Table
  await page.getByRole('button', { name: 'Administration', exact: true }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_admin_users_rbac.png') })

  // 11. User Deactivation Modal
  await page.getByRole('button', { name: 'Deactivate' }).first().click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_user_deactivate_confirm.png') })
  await page.getByRole('button', { name: 'Cancel' }).click()

  // 12. Security Audit Logs Table
  await page.getByRole('button', { name: /Security Audit Logs/i }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_admin_audit_logs.png') })

  // 13. Audit Event Inspection Modal
  await page.getByRole('button', { name: 'Inspect' }).first().click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_admin_audit_inspection.png') })
  await page.getByRole('button', { name: 'Close', exact: true }).click()

  // 14. Tablet View (768px) - Documents
  await page.setViewportSize({ width: 768, height: 1024 })
  await page.getByLabel('Open navigation menu').click()
  await page.getByRole('button', { name: 'Documents', exact: true }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_tablet_768px_documents.png') })

  // 15. Tablet View (768px) - Collections
  await page.getByLabel('Open navigation menu').click()
  await page.getByRole('button', { name: 'Collections', exact: true }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_tablet_768px_collections.png') })

  // 16. Mobile View (390px) - Admin
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByLabel('Open navigation menu').click()
  await page.getByRole('button', { name: 'Administration', exact: true }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: path.join(artifactDir, 'screenshot_stage5_mobile_390px_admin.png') })
})
