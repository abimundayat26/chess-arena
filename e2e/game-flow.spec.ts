import { expect, test, type Page } from "@playwright/test"
import { Chess } from "chess.js"

function withoutRunningClock(state: Record<string, unknown>) {
  const { white_clock_ms: _white, black_clock_ms: _black, ...rest } = state
  void _white
  void _black
  return rest
}

async function authoritativeState(page: Page, gameId: string) {
  const response = await page.request.get(`/api/games/${gameId}`)
  expect(response.status()).toBe(200)
  const state = await response.json()
  const replay = new Chess()
  replay.loadPgn(state.pgn)
  expect(replay.fen()).toBe(state.fen)
  expect(state.side_to_move).toBe(replay.turn() === "w" ? "white" : "black")
  expect(state.legal_moves.slice().sort()).toEqual(
    state.game_status === "playing"
      ? replay
          .moves({ verbose: true })
          .map((move) => `${move.from}${move.to}${move.promotion ?? ""}`)
          .sort()
      : []
  )
  expect(state.result === "*").toBe(state.game_status === "playing")
  expect(state.termination_reason === null).toBe(
    state.game_status === "playing"
  )
  return state
}

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
  await authoritativeState(page, gameId)
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
  await authoritativeState(page, gameId)
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
  await authoritativeState(page, gameId)
  expect(final.game_status).toBe("game-over")
  expect(final.termination_reason).toBe("resignation")
  for (const [path, body] of [
    ["moves", { uci: "e7e5" }],
    ["resign", { color: "white" }],
    ["draw-offer", { accepted: true }],
  ] as const) {
    const repeated = await page.request.post(`/api/games/${gameId}/${path}`, {
      data: body,
    })
    expect(repeated.status()).toBe(409)
  }
  expect(withoutRunningClock(await authoritativeState(page, gameId))).toEqual(withoutRunningClock(final))
  await expect(page.getByRole("button", { name: "Resign" })).toHaveCount(0)
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
  await authoritativeState(page, gameId)
  expect(final.result).toBe("1/2-1/2")
  expect(final.termination_reason).toBe("draw_agreement")
})

for (const [piece, san, suffix] of [
  ["Queen", "bxa8=Q", "q"],
  ["Knight", "bxa8=N", "n"],
] as const)
  test(`promotion to ${piece} uses UCI and reconciles after a rejected stale move`, async ({
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
    await expect(
      page.getByRole("button", { name: /^b7 white p$/ })
    ).toBeVisible()
    await page.getByRole("button", { name: /^b7 white p$/ }).click()
    await page.getByRole("button", { name: /^a8 black r$/ }).click()
    await expect(page.getByText("Promote pawn")).toBeVisible()
    await page.getByRole("button", { name: piece }).click()
    await expect
      .poll(async () => (await authoritativeState(page, gameId)).pgn)
      .toContain(san)
    await expect(
      page.getByRole("button", { name: `a8 white ${suffix}` })
    ).toBeVisible()
  })

test("backend checkmate moves the UI to Game Over", async ({ page }) => {
  const gameId = await startGame(page)
  for (const uci of ["f2f3", "e7e5", "g2g4", "d8h4"])
    await backendMove(page, gameId, uci)
  await syncStaleBoard(page, 409)
  await authoritativeState(page, gameId)
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
  await authoritativeState(page, gameId)
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
  await authoritativeState(page, gameId)
  await page.unroute(`**/api/games/${gameId}/moves`)
  await page.getByRole("button", { name: "Continue game" }).click()
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/games/${gameId}`)).json())
          .side_to_move
    )
    .toBe("white")
  await authoritativeState(page, gameId)
})

test("a rejected API move preserves the authoritative position and remains retryable", async ({
  page,
}) => {
  const gameId = await startGame(page)
  const initial = await authoritativeState(page, gameId)
  await page.route(`**/api/games/${gameId}/moves`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Try again"}',
    })
  )
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  await expect(
    page.getByRole("alert").filter({ hasText: "Try again" })
  ).toBeVisible()
  expect(withoutRunningClock(await authoritativeState(page, gameId))).toEqual(withoutRunningClock(initial))
  await expect(page.getByRole("button", { name: /^e2 white p$/ })).toBeVisible()
  await page.unroute(`**/api/games/${gameId}/moves`)
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  await expect(page.getByRole("button", { name: /^e4 white p$/ })).toBeVisible()
  expect((await authoritativeState(page, gameId)).pgn).toContain("e4")
})

test("failed refresh locks actions until the server state is recovered", async ({
  page,
}) => {
  const gameId = await startGame(page)
  await page.route(`**/api/games/${gameId}/moves`, async (route) => {
    await route.fetch()
    await route.abort("failed")
  })
  await page.route(`**/api/games/${gameId}`, (route) => route.abort("failed"))
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  await expect(page.getByRole("button", { name: "Retry sync" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Resign" })).toBeDisabled()
  await expect(page.getByRole("button", { name: /^e2 white p$/ })).toBeVisible()
  expect((await authoritativeState(page, gameId)).pgn).toContain("e4")
  await page.unroute(`**/api/games/${gameId}`)
  await page.unroute(`**/api/games/${gameId}/moves`)
  await page.getByRole("button", { name: "Retry sync" }).click()
  await expect(page.getByRole("button", { name: /^e4 white p$/ })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry sync" })).toHaveCount(0)
})

test("a lost resignation response still ends from the server result", async ({
  page,
}) => {
  const gameId = await startGame(page)
  await page.route(`**/api/games/${gameId}/resign`, async (route) => {
    await route.fetch()
    await route.abort("failed")
  })
  await page.getByRole("button", { name: "Resign" }).click()
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Resign" })
    .click()
  await expect(page.getByText("Resignation")).toBeVisible()
  const final = await authoritativeState(page, gameId)
  expect(final.game_status).toBe("game-over")
  expect(final.result).toBe("0-1")
  expect(final.termination_reason).toBe("resignation")
  await expect(page.getByRole("button", { name: "Resign" })).toHaveCount(0)
})

test("backend repetition result replaces a stale active board", async ({
  page,
}) => {
  const gameId = await startGame(page)
  for (const uci of [
    "g1f3",
    "g8f6",
    "f3g1",
    "f6g8",
    "g1f3",
    "g8f6",
    "f3g1",
    "f6g8",
  ])
    await backendMove(page, gameId, uci)
  await syncStaleBoard(page, 409)
  await expect(page.getByText("Threefold repetition")).toBeVisible()
  const final = await authoritativeState(page, gameId)
  expect(final.result).toBe("1/2-1/2")
  expect(final.termination_reason).toBe("repetition")
})

test("a game lost by the backend can return to setup", async ({ page }) => {
  const gameId = await startGame(page)
  await page.route(`**/api/games/${gameId}/moves`, (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: '{"detail":"Game not found"}',
    })
  )
  await page.route(`**/api/games/${gameId}`, (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: '{"detail":"Game not found"}',
    })
  )
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  await expect(page.getByRole("button", { name: "Retry sync" })).toBeVisible()
  await page.getByRole("button", { name: "New setup" }).click()
  await expect(page.getByRole("button", { name: "Start Game" })).toBeVisible()
})

test("selected clock runs and legal move receives increment", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "3+2", exact: true }).click()
  const created = page.waitForResponse((response) =>
    response.url().endsWith("/api/games") && response.request().method() === "POST"
  )
  await page.getByRole("button", { name: "Start Game" }).click()
  const initial = await (await created).json()
  expect(initial.time_control).toBe("3+2")
  expect(initial.white_clock_ms).toBe(180000)
  await expect(page.getByRole("timer", { name: "You clock" })).toHaveText("03:00")
  await expect(page.getByRole("timer", { name: "Claude Sonnet clock" })).toHaveText("03:00")
  await expect(page.getByRole("timer", { name: "You clock" })).toHaveText("02:59", { timeout: 3000 })
  const moved = page.waitForResponse((response) => response.url().includes("/moves") && response.request().method() === "POST")
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  const state = await (await moved).json()
  expect(state.white_clock_ms).toBeGreaterThan(180000)
  expect(state.white_clock_ms).toBeLessThan(182000)
  expect(state.active_clock).toBe("black")
  await expect(page.getByRole("timer", { name: "You clock" })).toHaveText("03:01")
  await expect(page.getByRole("timer", { name: "Claude Sonnet clock" })).toHaveText("02:59", { timeout: 3000 })
})

test("timeout from authoritative refresh opens Game Over", async ({ page }) => {
  const gameId = await startGame(page)
  let supplied = false
  await page.route(`**/api/games/${gameId}`, async (route) => {
    const response = await route.fetch()
    const state = await response.json()
    supplied = true
    await route.fulfill({ response, json: {
      ...state,
      white_clock_ms: 0,
      active_clock: null,
      game_status: "game-over",
      result: "0-1",
      termination_reason: "timeout",
      legal_moves: [],
    } })
  })
  await expect(page.getByText("Timeout")).toBeVisible({ timeout: 5000 })
  expect(supplied).toBeTruthy()
  await expect(page.getByRole("button", { name: "Resign" })).toHaveCount(0)
})

test("a move rejected by timeout reconciles to the server result", async ({ page }) => {
  const gameId = await startGame(page)
  let timedOut = false
  await page.route(`**/api/games/${gameId}/moves`, async (route) => {
    timedOut = true
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: '{"detail":"Game is over"}',
    })
  })
  await page.route(`**/api/games/${gameId}`, async (route) => {
    const response = await route.fetch()
    const state = await response.json()
    await route.fulfill({
      response,
      json: timedOut
        ? {
            ...state,
            white_clock_ms: 0,
            active_clock: null,
            game_status: "game-over",
            result: "0-1",
            termination_reason: "timeout",
            legal_moves: [],
          }
        : state,
    })
  })
  await page.getByRole("button", { name: /^e2 white p$/ }).click()
  await page.getByRole("button", { name: /^e4$/ }).click()
  await expect(page.getByText("Timeout")).toBeVisible()
  await expect(page.getByText("0–1").first()).toBeVisible()
  await expect(page.getByRole("button", { name: "Resign" })).toHaveCount(0)
})

test("rejected stale move reconciles both clocks from the API", async ({ page }) => {
  const gameId = await startGame(page)
  await backendMove(page, gameId, "e2e4")
  await syncStaleBoard(page, 400)
  const state = await authoritativeState(page, gameId)
  await expect(page.getByRole("button", { name: /^e4 white p$/ })).toBeVisible()
  const whiteLabel = `${Math.floor(Math.ceil(state.white_clock_ms / 1000) / 60).toString().padStart(2, "0")}:${(Math.ceil(state.white_clock_ms / 1000) % 60).toString().padStart(2, "0")}`
  await expect(page.getByRole("timer", { name: "You clock" })).toHaveText(whiteLabel)
  await expect(page.getByRole("timer", { name: "Claude Sonnet clock" })).toContainText("10:")
})
