import { expect, test, type Page } from "@playwright/test"

async function routeFakeProvider(page: Page, terminalOnTurn = false) {
  let gameId = ""
  let modelTurns = 0
  const drawBodies: string[] = []
  const decorate = (state: Record<string, unknown>) => ({
    ...state,
    model_provider: "openai",
    model_color: "black",
    context_level: "game_context",
    illegal_model_move_count: 2,
  })
  await page.route("**/api/providers", (route) => route.fulfill({ json: [{ provider: "openai", model: "Test model" }] }))
  await page.route("**/api/games**", async (route) => {
    const url = route.request().url()
    const method = route.request().method()
    if (url.endsWith("/api/games") && method === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>
      expect(body.model_provider).toBe("openai")
      expect(body.model_color).toBe("black")
      expect(body.context_level).toBe("game_context")
      const response = await route.fetch({ postData: JSON.stringify({ time_control: body.time_control }) })
      const state = await response.json()
      gameId = state.game_id
      await route.fulfill({ response, json: decorate(state) })
      return
    }
    if (url.endsWith("/model-turn")) {
      modelTurns++
      if (terminalOnTurn) {
        const response = await page.request.get(`/api/games/${gameId}`)
        const state = await response.json()
        await route.fulfill({ json: decorate({ ...state, game_status: "game-over", result: "1-0", termination_reason: "timeout", active_clock: null, black_clock_ms: 0, legal_moves: [] }) })
      } else if (modelTurns === 1) {
        await route.fulfill({ status: 502, json: { detail: "secret upstream provider error" } })
      } else {
        const response = await page.request.post(`/api/games/${gameId}/moves`, { data: { uci: "e7e5" } })
        await route.fulfill({ json: decorate(await response.json()) })
      }
      return
    }
    if (url.endsWith("/draw-offer")) {
      drawBodies.push(route.request().postData() ?? "")
      const response = await page.request.post(`/api/games/${gameId}/draw-offer`, { data: { accepted: true } })
      await route.fulfill({ json: decorate(await response.json()) })
      return
    }
    if (url.endsWith("/analysis")) {
      await route.fulfill({ json: { status: "unavailable", reason: "engine_unavailable" } })
      return
    }
    const response = await route.fetch()
    await route.fulfill({ response, json: decorate(await response.json()) })
  })
  return { modelTurns: () => modelTurns, drawBodies }
}

async function startModelGame(page: Page) {
  await page.goto("/")
  await page.getByRole("button", { name: /Test model/ }).click()
  await page.getByRole("button", { name: "Start Game" }).click()
  await expect(page.getByRole("button", { name: /^e2 white p$/ })).toBeVisible()
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
}

test("configured model retries after a safe error, then decides a draw", async ({ page }) => {
  const fake = await routeFakeProvider(page)
  await startModelGame(page)
  await expect(page.getByRole("button", { name: "Retry model turn" })).toBeVisible()
  await expect(page.getByText("secret upstream provider error")).toHaveCount(0)
  await page.getByRole("button", { name: "Retry model turn" }).click()
  await expect(page.getByRole("button", { name: /^e5 black p$/ })).toBeVisible()
  expect(fake.modelTurns()).toBe(2)
  await page.getByRole("button", { name: "Offer Draw" }).click()
  await expect(page.getByText("Draw agreement")).toBeVisible()
  await expect(page.getByText("Illegal AI moves").locator("..")).toContainText("2")
  await expect(page.getByText("Accuracy", { exact: true })).toHaveCount(0)
  expect(fake.drawBodies).toEqual(["{}"])
})

test("configured model timeout opens Game Over", async ({ page }) => {
  await routeFakeProvider(page, true)
  await startModelGame(page)
  await expect(page.getByText("Timeout")).toBeVisible()
  await expect(page.getByRole("button", { name: "Resign" })).toHaveCount(0)
})
