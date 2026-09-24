import { expect, test, type Page } from "@playwright/test"

async function startGame(page: Page): Promise<string> {
  await page.goto("/")
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/games") &&
      response.request().method() === "POST"
  )
  await page.getByRole("button", { name: "Start Game" }).click()
  const gameId = (await (await created).json()).game_id as string
  await expect(page.getByRole("button", { name: /^e2 white p$/ })).toBeVisible()
  return gameId
}

async function backendMove(page: Page, gameId: string, uci: string) {
  const response = await page.request.post(`/api/games/${gameId}/moves`, {
    data: { uci },
  })
  expect(response.ok(), `${uci}: ${await response.text()}`).toBeTruthy()
}

async function syncStaleBoard(page: Page, expectedStatus: number) {
  // The UI still shows the opening position. Submit a2a4 so the server rejects
  // it, then verify the client fetches the authoritative state.
  const rejected = page.waitForResponse(
    (response) =>
      response.url().includes("/moves") &&
      response.request().method() === "POST"
  )
  await page.getByRole("button", { name: /^a2 white p$/ }).click()
  await page.getByRole("button", { name: /^a4$/ }).click()
  expect((await rejected).status()).toBe(expectedStatus)
}

test("setup, local rejection, backend move, resignation, and new setup", async ({
  page,
}) => {
  const gameId = await startGame(page)
  const initial = await (await page.request.get(`/api/games/${gameId}`)).json()
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await expect(
    page
      .getByRole("button", { name: /^e4$/ })
      .locator("span.bg-board-legal-dot")
  ).toBeVisible()
  await page.getByRole("button", { name: /^e5$/ }).click()
  expect(
    (await (await page.request.get(`/api/games/${gameId}`)).json()).fen
  ).toBe(initial.fen)
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/games/${gameId}`)).json()).pgn
    )
    .toContain("e4")
  await page.getByRole("button", { name: "Resign" }).click()
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Resign" })
    .click()
  await expect(page.getByText("Resignation")).toBeVisible()
  const final = await (await page.request.get(`/api/games/${gameId}`)).json()
  expect(final.game_status).toBe("game-over")
  expect(final.termination_reason).toBe("resignation")
  await page.getByRole("button", { name: "New setup" }).click()
  await expect(page.getByRole("button", { name: "Start Game" })).toBeVisible()
})

test("declined and accepted draws use the backend", async ({ page }) => {
  const gameId = await startGame(page)
  await page.evaluate(() => {
    Math.random = () => 1
  })
  await page.getByRole("button", { name: "Offer Draw" }).click()
  await expect(page.getByText("Draw declined")).toBeVisible()
  expect(
    (await (await page.request.get(`/api/games/${gameId}`)).json()).game_status
  ).toBe("playing")
  await page.evaluate(() => {
    Math.random = () => 0
  })
  await page.getByRole("button", { name: "Offer Draw" }).click()
  await expect(page.getByText("Draw agreement")).toBeVisible()
  const final = await (await page.request.get(`/api/games/${gameId}`)).json()
  expect(final.result).toBe("1/2-1/2")
  expect(final.termination_reason).toBe("draw_agreement")
})

test("promotion uses UCI and reconciles after a rejected stale move", async ({
  page,
}) => {
  const gameId = await startGame(page)
  for (const uci of [
    "a2a4",
    "h7h5",
    "a4a5",
    "h5h4",
    "a5a6",
    "h4h3",
    "a6b7",
    "h3g2",
  ]) {
    await backendMove(page, gameId, uci)
  }
  await syncStaleBoard(page, 400)
  await expect(page.getByRole("button", { name: /^b7 white p$/ })).toBeVisible()
  await page.getByRole("button", { name: /^b7 white p$/ }).click()
  await page.getByRole("button", { name: /^a8 black r$/ }).click()
  await expect(page.getByText("Promote pawn")).toBeVisible()
  await page.getByRole("button", { name: "Queen" }).click()
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/games/${gameId}`)).json()).pgn
    )
    .toContain("bxa8=Q")
  await expect(page.getByRole("button", { name: /^a8 white q$/ })).toBeVisible()
})

test("backend checkmate moves the UI to Game Over", async ({ page }) => {
  const gameId = await startGame(page)
  for (const uci of ["f2f3", "e7e5", "g2g4", "d8h4"])
    await backendMove(page, gameId, uci)
  await syncStaleBoard(page, 409)
  await expect(page.getByText("Checkmate")).toBeVisible()
  await expect(page.getByText("0–1").first()).toBeVisible()
})

test("black player can drag a move after the mocked opponent moves through the API", async ({
  page,
}) => {
  await page.goto("/")
  await page.getByRole("button", { name: "Black", exact: true }).click()
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/games") &&
      response.request().method() === "POST"
  )
  await page.getByRole("button", { name: "Start Game" }).click()
  const gameId = (await (await created).json()).game_id as string
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/games/${gameId}`)).json())
          .side_to_move
    )
    .toBe("black")
  const before = await (await page.request.get(`/api/games/${gameId}`)).json()
  expect(before.pgn).not.toBe("*")
  await page
    .locator('button[aria-label="g8 black n"] [draggable="true"]')
    .dragTo(page.getByRole("button", { name: /^f6$/ }))
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/games/${gameId}`)).json()).pgn
    )
    .toContain("Nf6")
})

test("a lost move response is reconciled from the backend", async ({
  page,
}) => {
  const gameId = await startGame(page)
  await page.route(`**/api/games/${gameId}/moves`, async (route) => {
    await route.fetch()
    await route.abort("failed")
  })
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  await expect(page.getByRole("button", { name: /^e4 white p$/ })).toBeVisible()
  await expect(
    page.getByRole("alert").filter({ hasText: "Cannot reach the game server" })
  ).toBeVisible()
  expect(
    (await (await page.request.get(`/api/games/${gameId}`)).json()).pgn
  ).toContain("e4")
  await page.unroute(`**/api/games/${gameId}/moves`)
  await page.getByRole("button", { name: "Continue game" }).click()
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/games/${gameId}`)).json())
          .side_to_move
    )
    .toBe("white")
})
