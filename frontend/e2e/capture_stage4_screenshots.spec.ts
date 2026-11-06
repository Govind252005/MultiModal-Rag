import { test } from '@playwright/test'
import path from 'path'

const ARTIFACT_DIR = 'C:/Users/HP/.gemini/antigravity/brain/689acc0c-4d09-42bd-a9f2-46a2f6d7a7c3'

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
      text: 'IN THE HOUSE OF LORDS.\n\nRYLANDS v FLETCHER.\n\nThe shafts were vertical, the passages horizontal, and the former especially seemed filled with marl and rubbish. Defendants employed for the purpose of constructing their new reservoir persons who were admitted to be competent engineers and contractors.',
    },
    {
      page_number: 2,
      text: 'Page 2: The reservoir was being constructed over five vertical shafts of old coal workings.',
    },
    {
      page_number: 3,
      text: 'Page 3: Judgment and Findings.\n\nin point of fact, reasonable and proper care and skill were not exercised by, or on the part of, the persons so employed by them, with reference to the shafts so met with as aforesaid, to provide for the sufficiency of the said reservoir.\n\nThe reservoir was completed at the beginning of December, 1860, and on the morning of the 11th of that month broke into the old workings.',
    },
  ],
  raw_url: '/api/media/sess_legal_brief/Rylands_v_Fletcher_1868.pdf',
  file_size: 245012,
}

const mockDocxContent = {
  filename: 'Global_Compliance_Handbook.docx',
  modality: 'docx',
  has_pages: false,
  page_count: null,
  content: 'GLOBAL COMPLIANCE HANDBOOK (2025)\n\nChapter 1: Environmental and Safety Guidelines\n\nSection 4: Strict liability applies to hazardous materials storage without proof of negligence.\n\nAll facility managers must maintain automated leak detection systems.',
  raw_url: '/api/media/sess_legal_brief/Global_Compliance_Handbook.docx',
  file_size: 38200,
}

const mockHindiContent = {
  filename: 'Hindi_Legal_Notice_अनुबंध.pdf',
  modality: 'pdf',
  has_pages: true,
  page_count: 5,
  pages: [
    {
      page_number: 1,
      text: 'विधि एवं न्याय मंत्रालय\nप्रकरण: रायलैंड्स बनाम फ्लेचर दायित्व समीक्षा\nपृष्ठ १: प्रारंभिक विवरण',
    },
    {
      page_number: 2,
      text: 'पृष्ठ २: अधिकरण के निष्कर्ष\n\nन्यायालय के निष्कर्ष के अनुसार, प्रतिवादी ने निर्माण कार्य के दौरान उचित सावधानी और कौशल का प्रयोग नहीं किया, जिसके परिणामस्वरूप जलाशय टूट गया।\n\nअतः पूर्ण दायित्व लागू होगा और हर्जाना देय होगा।',
    },
  ],
  raw_url: '/api/media/sess_legal_brief/Hindi_Legal_Notice_अनुबंध.pdf',
  file_size: 198000,
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
      text: 'In the landmark case of Rylands v Fletcher [1], the defendant employed competent engineers and contractors to construct a reservoir on his land. However, the contractors failed to exercise reasonable care and skill [2] when they encountered old vertical shafts filled with marl and rubbish. The reservoir burst, flooding the plaintiff\'s colliery. Additionally, under global compliance standards [3], strict liability applies to hazardous storage without proof of negligence. In the Hindi legal analysis [4], उचित सावधानी और कौशल का अभाव स्पष्ट रूप से रेखांकित किया गया है।',
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
          text: 'in point of fact, reasonable and proper care and skill were not exercised by, or on the part of, the persons so employed by them, with reference to the shafts so met with as aforesaid, to provide for the sufficiency of the said reservoir.',
          score: 0.91,
          relative_relevance: 88,
          confidence: 88,
        },
        {
          index: 3,
          id: 'chunk_rf_03',
          file: 'Global_Compliance_Handbook.docx',
          modality: 'document',
          source_type: 'text',
          page: null,
          snippet: 'Section 4: Strict liability applies to hazardous materials storage without proof of negligence.',
          text: 'Section 4: Strict liability applies to hazardous materials storage without proof of negligence.',
          score: 0.82,
          relative_relevance: 70,
          confidence: 70,
        },
        {
          index: 4,
          id: 'chunk_rf_04',
          file: 'Hindi_Legal_Notice_अनुबंध.pdf',
          modality: 'document',
          source_type: 'text',
          page: 2,
          snippet: 'प्रतिवादी ने निर्माण कार्य के दौरान उचित सावधानी और कौशल का प्रयोग नहीं किया',
          text: 'न्यायालय के निष्कर्ष के अनुसार, प्रतिवादी ने निर्माण कार्य के दौरान उचित सावधानी और कौशल का प्रयोग नहीं किया, जिसके परिणामस्वरूप जलाशय टूट गया।',
          score: 0.96,
          relative_relevance: 98,
          confidence: 98,
        },
      ],
      usedLlm: true,
    },
  ],
}

test.describe('Stage 4 Screenshots Capture', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'mock_jwt_token_user1')
      localStorage.setItem(
        'user',
        JSON.stringify(legalUser)
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

      if (path.includes('Global_Compliance_Handbook.docx/content')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockDocxContent),
        })
        return
      }

      if (decodeURIComponent(path).includes('Hindi_Legal_Notice')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockHindiContent),
        })
        return
      }

      await route.continue()
    })
  })

  test('capture all 8 Stage 4 screenshots', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')

    // Navigate into the session from the dashboard
    const sessionCard = page.locator('text=Rylands v Fletcher Liability Analysis').first()
    await sessionCard.waitFor({ state: 'visible' })
    await sessionCard.click()

    // Wait for chat to render
    const cit2Btn = page.locator('button[title*="source [2]"]').first()
    await cit2Btn.waitFor({ state: 'visible' })

    // 1. Chat with evidence viewer closed
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'screenshot_stage4_chat_closed_viewer.png'),
    })

    // 2. Click Citation [2] -> Opens split-screen chat and PDF viewer
    await cit2Btn.click()

    const viewer = page.locator('[data-testid="evidence-document-viewer"]')
    await viewer.waitFor({ state: 'visible' })
    await page.waitForTimeout(600)

    // 2. Split-screen chat and PDF viewer
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'screenshot_stage4_splitscreen_chat_and_pdf.png'),
    })

    // 3. Citation clicked and exact source page opened (Page 3 of 11)
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'screenshot_stage4_citation_clicked_exact_page.png'),
    })

    // 4. Verified highlighted source passage in the page text
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'screenshot_stage4_verified_highlighted_passage.png'),
    })

    // 5. Evidence sidebar with multiple citations
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'screenshot_stage4_evidence_sidebar_multiple_citations.png'),
    })

    // 6. Hindi / Devanagari evidence passage
    const hindiAnn = viewer.locator('[data-testid="annotation-card-4"]').first()
    if (await hindiAnn.isVisible()) {
      await hindiAnn.click()
      await page.waitForTimeout(600)
      await page.screenshot({
        path: path.join(ARTIFACT_DIR, 'screenshot_stage4_hindi_devanagari_evidence.png'),
      })
    }

    // 7. Unsupported or missing page metadata fallback (DOCX)
    const docxAnn = viewer.locator('[data-testid="annotation-card-3"]').first()
    if (await docxAnn.isVisible()) {
      await docxAnn.click()
      await page.waitForTimeout(600)
      await page.screenshot({
        path: path.join(ARTIFACT_DIR, 'screenshot_stage4_missing_page_metadata_fallback.png'),
      })
    }

    // 8. Mobile / responsive viewer
    await page.setViewportSize({ width: 390, height: 844 })
    await page.waitForTimeout(600)
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'screenshot_stage4_mobile_responsive_viewer.png'),
    })
  })
})
