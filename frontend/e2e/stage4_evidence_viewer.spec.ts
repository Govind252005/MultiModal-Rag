import { test, expect } from '@playwright/test'

const legalUser = {
  id: 'user_1',
  email: 'legal.counsel@enterprise.org',
  role: 'user',
  org_id: 'enterprise_legal',
}

const mockPdfContent = {
  filename: 'Rylands_v_Fletcher_1868.pdf',
  modality: 'pdf',
  has_pages: true,
  page_count: 11,
  pages: [
    {
      page_number: 1,
      text: 'IN THE HOUSE OF LORDS.\n\nRYLANDS v FLETCHER.\n\nThe shafts were vertical, the passages horizontal, and the former especially seemed filled with marl and rubbish. Defendants employed for the purpose of constructing their new reservoir persons who were admitted to be competent engineers.',
    },
    {
      page_number: 2,
      text: 'Page 2: Statement of facts continued. The bed of the reservoir met with five old shafts.',
    },
    {
      page_number: 3,
      text: 'Page 3: Findings of the arbitrator.\n\nin point of fact, reasonable and proper care and skill were not exercised by, or on the part of, the persons so employed by them, with reference to the shafts so met with as aforesaid, to provide for the sufficiency of the said reservoir.\n\nThe reservoir was completed at the beginning of December, 1860.',
    },
  ],
  raw_url: '/api/media/sess_legal_brief/Rylands_v_Fletcher_1868.pdf',
  file_size: 245012,
}

const mockDocxContent = {
  filename: 'Employment_Agreement_2024.docx',
  modality: 'docx',
  has_pages: false,
  page_count: null,
  content: 'EMPLOYMENT AGREEMENT\n\nSection 1: Definitions and Interpretation\nSection 2: Scope of Engagement\n\nClause 14.2: The governing law shall be the laws of England and Wales.',
  raw_url: '/api/media/sess_legal_brief/Employment_Agreement_2024.docx',
  file_size: 45100,
}

const mockLegalSession = {
  id: 'sess_legal_brief',
  title: 'Rylands v Fletcher Liability Analysis',
  messages: [
    {
      role: 'user',
      text: 'What were the material facts and rule established in Rylands v Fletcher?',
    },
    {
      role: 'assistant',
      text: 'In the landmark case of Rylands v Fletcher [1], the defendant employed competent engineers and contractors to construct a reservoir on his land. However, the contractors failed to exercise reasonable care and skill [2] when they encountered old vertical shafts filled with marl and rubbish. The reservoir burst, flooding the plaintiff\'s colliery. The court held that a person who brings something likely to do mischief onto their land is strictly liable for the natural consequences of its escape [3].',
      citations: [
        {
          index: 1,
          id: 'chunk_rf_01',
          file: 'Rylands_v_Fletcher_1868.pdf',
          modality: 'document',
          source_type: 'text',
          page: 1,
          snippet: 'The shafts were vertical, the passages horizontal, and the former especially seemed filled with marl and rubbish.',
          text: 'The shafts were vertical, the passages horizontal, and the former especially seemed filled with marl and rubbish.',
          score: 0.94,
          relative_relevance: 95,
          confidence: 95,
        },
        {
          index: 2,
          id: 'chunk_rf_02',
          file: 'Rylands_v_Fletcher_1868.pdf',
          modality: 'document',
          source_type: 'text',
          page: 3,
          snippet: 'reasonable and proper care and skill were not exercised by, or on the part of, the persons so employed by them',
          text: 'in point of fact, reasonable and proper care and skill were not exercised by, or on the part of, the persons so employed by them, with reference to the shafts so met with as aforesaid.',
          score: 0.91,
          relative_relevance: 88,
          confidence: 88,
        },
        {
          index: 3,
          id: 'chunk_rf_03',
          file: 'Employment_Agreement_2024.docx',
          modality: 'document',
          source_type: 'text',
          page: null,
          snippet: 'Clause 14.2: The governing law shall be the laws of England and Wales.',
          text: 'Clause 14.2: The governing law shall be the laws of England and Wales.',
          score: 0.85,
          relative_relevance: 75,
          confidence: 75,
        },
      ],
      usedLlm: true,
    },
  ],
}

test.describe('Stage 4: Enterprise Evidence & Document Viewer', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'mock_jwt_token_user1')
      localStorage.setItem(
        'user',
        JSON.stringify({
          id: 'user_1',
          email: 'legal.counsel@enterprise.org',
          role: 'user',
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
          body: JSON.stringify({ user: legalUser }),
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
            index: { text_items: 42, image_items: 8 },
          }),
        })
        return
      }

      if (path === '/api/active-provider' || path === '/api/llm/active') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            provider: 'ollama',
            model: 'qwen3:4b',
            mode: 'local',
            is_local: true,
          }),
        })
        return
      }

      if (path === '/api/providers') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            default: 'ollama',
            providers: [{ name: 'ollama', label: 'Local Qwen', local: true, model: 'qwen3:4b' }],
          }),
        })
        return
      }

      if (path === '/api/sessions') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            sessions: [
              {
                id: 'sess_legal_brief',
                title: 'Rylands v Fletcher Liability Analysis',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                message_count: 2,
              },
            ],
          }),
        })
        return
      }

      if (path === '/api/sessions/sess_legal_brief') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockLegalSession),
        })
        return
      }

      if (path.includes('Rylands_v_Fletcher_1868.pdf/content')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockPdfContent),
        })
        return
      }

      if (path.includes('Employment_Agreement_2024.docx/content')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockDocxContent),
        })
        return
      }

      await route.continue()
    })
  })

  test('clicking citation [2] opens split-screen viewer on exact document and page 3 with verified highlight', async ({ page }) => {
    await page.goto('/')

    // Click on the recent session in the Dashboard to enter chat directly with that session
    const sessionCard = page.locator('text=Rylands v Fletcher Liability Analysis').first()
    await expect(sessionCard).toBeVisible({ timeout: 10000 })
    await sessionCard.click()

    // Verify chat assistant response is rendered with citation pills
    const citation2 = page.locator('button[title*="source [2]"]').first()
    await expect(citation2).toBeVisible({ timeout: 10000 })

    // Click citation [2]
    await citation2.click()

    // Verify split-screen document viewer opens
    const viewer = page.locator('[data-testid="evidence-document-viewer"]')
    await expect(viewer).toBeVisible({ timeout: 5000 })

    // Verify correct document name is displayed
    await expect(viewer.getByRole('heading', { name: 'Rylands_v_Fletcher_1868.pdf' })).toBeVisible()

    // Verify correct page 3 is opened
    await expect(viewer.getByText('Page 3 of 11')).toBeVisible()

    // Verify exact highlighted passage appears in the page text
    const highlight = viewer.locator('mark')
    await expect(highlight).toBeVisible()
    await expect(highlight).toContainText('reasonable and proper care and skill were not exercised')

    // Verify annotations sidebar contains multiple citations
    await expect(viewer.getByRole('heading', { name: /Annotations & Evidence/i })).toBeVisible()
  })

  test('clicking citation [3] for DOCX format displays verified text evidence with highlight and active evidence badge', async ({ page }) => {
    await page.goto('/')

    const sessionCard = page.locator('text=Rylands v Fletcher Liability Analysis').first()
    await expect(sessionCard).toBeVisible({ timeout: 10000 })
    await sessionCard.click()

    // Click citation [3]
    const citation3 = page.locator('button[title*="source [3]"]').first()
    await expect(citation3).toBeVisible({ timeout: 10000 })
    await citation3.click()

    const viewer = page.locator('[data-testid="evidence-document-viewer"]')
    await expect(viewer).toBeVisible({ timeout: 5000 })

    // Verify DOCX document name
    await expect(viewer.getByRole('heading', { name: 'Employment_Agreement_2024.docx' })).toBeVisible()

    // Verify active supporting evidence badge is present
    await expect(viewer.getByText('Active Supporting Evidence')).toBeVisible()

    // Verify highlighted text in DOCX text
    const highlight = viewer.locator('mark')
    await expect(highlight).toContainText('The governing law shall be the laws of England and Wales')
  })

  test('switching citations in annotations sidebar smoothly jumps between document pages', async ({ page }) => {
    await page.goto('/')

    const sessionCard = page.locator('text=Rylands v Fletcher Liability Analysis').first()
    await expect(sessionCard).toBeVisible({ timeout: 10000 })
    await sessionCard.click()

    // Open citation [2] (Page 3)
    const citation2 = page.locator('button[title*="source [2]"]').first()
    await citation2.click()

    const viewer = page.locator('[data-testid="evidence-document-viewer"]')
    await expect(viewer.getByText('Page 3 of 11')).toBeVisible()

    // In annotations sidebar, click annotation card for citation [1] (Page 1)
    const ann1 = viewer.locator('[data-testid="annotation-card-1"]').first()
    await ann1.click()

    // Document viewer jumps to Page 1
    await expect(viewer.getByText('Page 1 of 11')).toBeVisible()
    await expect(viewer.getByText(/IN THE HOUSE OF LORDS/i)).toBeVisible()
  })

  test('closing viewer restores full-width chat without losing messages or state', async ({ page }) => {
    await page.goto('/')

    const sessionCard = page.locator('text=Rylands v Fletcher Liability Analysis').first()
    await expect(sessionCard).toBeVisible({ timeout: 10000 })
    await sessionCard.click()

    // Open citation
    const citation1 = page.locator('button[title*="source [1]"]').first()
    await citation1.click()

    const viewer = page.locator('[data-testid="evidence-document-viewer"]')
    await expect(viewer).toBeVisible()

    // Click Close (X) button on viewer
    const closeBtn = viewer.locator('button[title="Close viewer"]')
    await closeBtn.click()

    // Viewer collapses
    await expect(viewer).not.toBeVisible()

    // Chat remains completely intact
    await expect(page.getByText(/In the landmark case of Rylands v Fletcher/i)).toBeVisible()
  })

  test('mobile viewport (390px) switches cleanly between Document and Annotations without squeezing text', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')

    const sessionCard = page.locator('text=Rylands v Fletcher Liability Analysis').first()
    await expect(sessionCard).toBeVisible({ timeout: 10000 })
    await sessionCard.click()

    // Open citation [2]
    const citation2 = page.locator('button[title*="source [2]"]').first()
    await citation2.click()

    const viewer = page.locator('[data-testid="evidence-document-viewer"]')
    await expect(viewer).toBeVisible()

    // On mobile, the mobile tab bar is visible
    const docTab = page.locator('[data-testid="mobile-tab-document"]')
    const annTab = page.locator('[data-testid="mobile-tab-annotations"]')
    await expect(docTab).toBeVisible()
    await expect(annTab).toBeVisible()

    // Document surface is visible and full width; sidebar is hidden
    const docSurface = page.locator('[data-testid="document-content-surface"]')
    const annSurface = page.locator('[data-testid="annotations-surface"]')
    await expect(docSurface).toBeVisible()
    await expect(annSurface).toBeHidden()

    // Switch to Annotations tab
    await annTab.click()
    await expect(annSurface).toBeVisible()
    await expect(docSurface).toBeHidden()

    // In annotations view, return button is visible
    const returnBtn = page.locator('[data-testid="return-to-document-btn"]')
    await expect(returnBtn).toBeVisible()

    // Clicking an annotation card preserves selection and returns to Document view
    const annCard1 = page.locator('[data-testid="annotation-card-1"]').first()
    await annCard1.click()

    // Document surface is restored to view and displays Page 1
    await expect(docSurface).toBeVisible()
    await expect(annSurface).toBeHidden()
    await expect(viewer.getByText('Page 1 of 11')).toBeVisible()
  })

  test('tablet viewport (768px) renders balanced split view and allows toggling Annotations', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('/')

    const sessionCard = page.locator('text=Rylands v Fletcher Liability Analysis').first()
    await expect(sessionCard).toBeVisible({ timeout: 10000 })
    await sessionCard.click()

    const citation2 = page.locator('button[title*="source [2]"]').first()
    await citation2.click()

    const viewer = page.locator('[data-testid="evidence-document-viewer"]')
    await expect(viewer).toBeVisible()

    // Document surface is visible with readable text
    const docSurface = page.locator('[data-testid="document-content-surface"]')
    await expect(docSurface).toBeVisible()

    // On 768px tablet, user can switch between Document and Annotations via responsive tabs
    const annTab = page.locator('[data-testid="mobile-tab-annotations"]')
    const docTab = page.locator('[data-testid="mobile-tab-document"]')
    await expect(annTab).toBeVisible()
    await expect(docTab).toBeVisible()

    await annTab.click()
    const annSurface = page.locator('[data-testid="annotations-surface"]')
    await expect(annSurface).toBeVisible()

    await docTab.click()
    await expect(docSurface).toBeVisible()
  })
})
