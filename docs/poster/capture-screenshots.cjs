const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");

const repoRoot = path.resolve(__dirname, "../..");
const assetsDir = path.join(__dirname, "assets");

const demoState = {
  vault: [
    {
      id: "vault-orb-playbook",
      title: "Opening Range Breakout Playbook",
      kind: "Article",
      source: "Strategy research",
      body:
        "Opening range breakout plan requiring relative volume confirmation, a clean premarket range, stop placement before entry, and no entries after 10:45 AM. The note highlights execution risks around chasing, early stop movement, and low-liquidity breakouts.",
      tags: ["orb", "risk-reward", "opening-range"],
      aiTags: ["strategy:orb", "entry:range-break", "risk:predefined-stop", "filter:rvol"],
      strategyInfo: {
        name: "ORB v3",
        summary:
          "Paper-test a stricter opening range breakout variant with relative volume and time-of-day filters.",
        setup: "High relative-volume stock breaking a 15-minute opening range near premarket high.",
        entry_rules: [
          "Wait for 15-minute opening range to complete",
          "Require RVOL above 1.8",
          "Enter only on confirmed break and hold"
        ],
        exit_rules: ["Partial at 1R", "Trail remainder with VWAP or 9 EMA", "No entries after 10:45 AM"],
        risk_rules: ["Stop below opening range midpoint", "No discretionary stop movement before 1R"],
        timeframe: "15m execution, 5m confirmation",
        indicators: ["VWAP", "RVOL", "9 EMA"],
        market: "US equities",
        confidence: 0.82
      },
      createdAt: "2026-07-06T09:00:00.000Z"
    },
    {
      id: "vault-vwap-loss-review",
      title: "VWAP Pullback Loss Review",
      kind: "Journal Note",
      source: "Post-trade review",
      body:
        "Loss cluster shows VWAP pullbacks underperform when the trader skips premarket planning, enters after three candles away from VWAP, or trades during anxious state after a prior loss.",
      tags: ["vwap-pullback", "loss-review", "emotional-state"],
      aiTags: ["leak:late-entry", "routine:missing-plan", "state:anxious"],
      strategyInfo: {
        name: "VWAP Pullback Guardrails",
        summary: "Avoid late VWAP entries and require routine completion before taking continuation setups.",
        setup: "Trend day pullback to VWAP with clean higher low.",
        entry_rules: ["Require planned levels before open", "Enter within one candle of VWAP reclaim"],
        exit_rules: ["Exit on failed reclaim", "Reduce size after first loss"],
        risk_rules: ["No trade if routine incomplete", "No chase after three extended candles"],
        timeframe: "5m",
        indicators: ["VWAP", "ATR"],
        market: "US equities",
        confidence: 0.76
      },
      createdAt: "2026-07-06T09:08:00.000Z"
    }
  ],
  journal: [
    {
      id: "journal-2026-07-01",
      date: "2026-07-01",
      title: "Focused open, followed plan",
      emotion: "focused",
      routineDone: true,
      body: "Completed premarket checklist, marked no-trade zones, and waited for first clean ORB trigger.",
      tags: ["routine-complete", "premarket-plan"],
      createdAt: "2026-07-01T13:20:00.000Z"
    },
    {
      id: "journal-2026-07-02",
      date: "2026-07-02",
      title: "Chased after first loss",
      emotion: "anxious",
      routineDone: false,
      body: "Skipped review after first loss and took a late VWAP pullback without defined stop. Mark as avoidable.",
      tags: ["routine-missed", "chasing", "loss-review"],
      createdAt: "2026-07-02T13:20:00.000Z"
    }
  ],
  trades: [
    {
      id: "trade-1",
      symbol: "NVDA",
      side: "long",
      entryDate: "2026-07-01",
      entryPrice: 122.4,
      exitPrice: 125.1,
      quantity: 100,
      fees: 1.5,
      strategy: "ORB v3",
      setup: "opening-range",
      emotion: "focused",
      notes: "Waited for RVOL confirmation and held first pullback.",
      createdAt: "2026-07-01T14:15:00.000Z"
    },
    {
      id: "trade-2",
      symbol: "AAPL",
      side: "long",
      entryDate: "2026-07-02",
      entryPrice: 213.2,
      exitPrice: 211.6,
      quantity: 80,
      fees: 1.2,
      strategy: "VWAP Pullback",
      setup: "late-entry",
      emotion: "anxious",
      notes: "Entered too far from VWAP after missing the planned reclaim.",
      createdAt: "2026-07-02T15:10:00.000Z"
    },
    {
      id: "trade-3",
      symbol: "TSLA",
      side: "short",
      entryDate: "2026-07-03",
      entryPrice: 242.5,
      exitPrice: 238.8,
      quantity: 60,
      fees: 1.4,
      strategy: "Opening Drive Fade",
      setup: "exhaustion",
      emotion: "calm",
      notes: "Followed stop and took partial at planned target.",
      createdAt: "2026-07-03T14:40:00.000Z"
    },
    {
      id: "trade-4",
      symbol: "AMD",
      side: "long",
      entryDate: "2026-07-04",
      entryPrice: 165.5,
      exitPrice: 166.9,
      quantity: 120,
      fees: 1.6,
      strategy: "ORB v3",
      setup: "opening-range",
      emotion: "focused",
      notes: "Clean break above premarket high with full routine completed.",
      createdAt: "2026-07-04T14:05:00.000Z"
    },
    {
      id: "trade-5",
      symbol: "META",
      side: "long",
      entryDate: "2026-07-05",
      entryPrice: 702.2,
      exitPrice: 699.4,
      quantity: 35,
      fees: 1.1,
      strategy: "VWAP Pullback",
      setup: "late-entry",
      emotion: "frustrated",
      notes: "Ignored no-trade-after-loss rule and moved stop early.",
      createdAt: "2026-07-05T16:20:00.000Z"
    }
  ]
};

async function main() {
  await fs.mkdir(assetsDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1500, height: 1050 },
    deviceScaleFactor: 2,
    colorScheme: "light"
  });

  await context.addInitScript((state) => {
    window.localStorage.setItem("quant-labs.workspace.v1", JSON.stringify(state));
  }, demoState);

  const page = await context.newPage();
  await page.route("http://localhost:8000/**", (route) => {
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "offline during poster capture" })
    });
  });
  await page.goto("http://localhost:3000/", { waitUntil: "networkidle" });

  await page.waitForSelector("#vault-panel", { timeout: 30000 });
  await page.locator("#vault-panel").screenshot({
    path: path.join(assetsDir, "app-vault-capture.png")
  });

  await page.getByRole("tab", { name: "Trades" }).click();
  await page.waitForSelector("#trades-panel");
  await page.locator("#trades-panel").screenshot({
    path: path.join(assetsDir, "app-trade-log.png")
  });

  await page.getByRole("tab", { name: "Insights" }).click();
  await page.waitForSelector("#insights-panel");
  await page.locator("#insights-panel").screenshot({
    path: path.join(assetsDir, "app-trading-insights.png")
  });

  await page.getByRole("tab", { name: "Map" }).click();
  await page.waitForSelector("#graph-panel");
  await page.locator("#graph-panel").screenshot({
    path: path.join(assetsDir, "app-obsidian-map.png")
  });

  await browser.close();
  console.log(`Screenshots written to ${path.relative(repoRoot, assetsDir)}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
