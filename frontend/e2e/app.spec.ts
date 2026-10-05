import { expect, test, type Page } from '@playwright/test'

const user = { id: 'e2e-user', email: 'e2e@example.com', role: 'user' }
const active = { provider: 'ollama', model: 'qwen3:4b', mode: 'local', status: 'active' }

async function mockApi(page: Page, loginOk = true) {
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.pathname === '/api/auth/login') {
      if (!loginOk) {
        await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: { message: 'Wrong email or password.' } }) })
        return
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ token: 'test-token', user }) })
      return
    }
    if (url.pathname === '/api/health') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', device: 'cpu', llm_available: true, llm_model: 'qwen3:4b', index: { text_items: 0, image_items: 0 } }) })
      return
    }
    if (url.pathname === '/api/sessions') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ sessions: [] }) })
      return
    }
    if (url.pathname === '/api/llm/active') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(active) })
      return
    }
    if (url.pathname === '/api/providers') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ default: 'ollama', providers: [{ name: 'ollama', label: 'Local Qwen (Ollama)', local: true, model: 'qwen3:4b', has_key: true, available: true, supports_images: false, supports_streaming: true }] }) })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
}

test('renders login and shows invalid credentials', async ({ page }) => {
  await mockApi(page, false)
  await page.goto('/')
  await page.getByPlaceholder('you@example.com').fill('bad@example.com')
  await page.getByPlaceholder('Your password').fill('wrong-password')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()
  await expect(page.getByText(/wrong email or password/i)).toBeVisible()
})

test('logs in and renders the authenticated application shell', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await page.getByPlaceholder('you@example.com').fill(user.email)
  await page.getByPlaceholder('Your password').fill('test-password')
  await page.locator('form').getByRole('button', { name: 'Sign In' }).click()
  await expect(page.getByText(/local qwen/i)).toBeVisible()
})