# Quant Labs Poster

This folder contains a 3 ft wide by 2 ft tall LaTeX research poster for the
Quant Labs / Trading Intelligence OS project.

## Files

- `quant-labs-poster.tex` - self-contained poster source.
- `quant-labs-poster.pdf` - generated poster output after compilation.
- `quant-labs-poster-preview.png` - rendered preview image for quick review.
- `quant-labs-poster-isef-redesign.pdf` - clearly named copy of the latest ISEF-style revision.
- `quant-labs-poster-isef-redesign-preview.png` - preview image for the latest ISEF-style revision.
- `assets/` - Playwright-captured app screenshots and copied logo assets used by the poster.
- `capture-screenshots.cjs` - reproducible screenshot capture script.

## Build

From this folder, compile with Tectonic:

```bash
tectonic quant-labs-poster.tex
```

If a full TeX Live install is available, this also works:

```bash
latexmk -pdf quant-labs-poster.tex
```

## Screenshot Capture

The app screenshots were captured from the local Next.js app with Playwright.
Run the web app first:

```bash
npm --prefix apps/web run dev
```

Then run the capture script from the repository root with Playwright available
on `NODE_PATH`:

```bash
npm install --prefix /private/tmp/quant-labs-playwright-capture playwright@1.57.0
NODE_PATH=/private/tmp/quant-labs-playwright-capture/node_modules node docs/poster/capture-screenshots.cjs
```

The script seeds demo workspace data in browser localStorage, blocks the API
health check so the local seed is used, and writes screenshots into
`docs/poster/assets`.

## Design Notes

The layout is a polished 36 in by 24 in landscape research poster:

- fixed 3 ft by 2 ft page size
- reduced dark header focused on project identity and the main claim
- three-column story flow: problem and approach, core memory graph, results and impact
- larger body type and fewer competing sections
- warm white background with dark teal, muted cyan, and soft green accents
- metric cards moved into the Results section
- dominant Obsidian-style relationship-map screenshot in the center column
- enlarged vault-capture, trade-log, and strategy-insights evidence screenshots
- generated-output block under Vault Capture to explain tags and strategy metadata
- strategy-insight output block under Evidence + Results to fill the right column
- full-width horizontal system pipeline with four readable product-flow cards
- Tech Stack row under System Overview with real TypeScript, Next.js, Tailwind,
  FastAPI, Postgres, and Playwright logos
- top header affiliation panel with GHP and GSU logos from the project image folder
- bottom Future Work Roadmap with six clear implementation steps
- reserved APA Sources area for final citations
- QR Links area with the project demo/repo QR code

The poster uses four Playwright-captured screenshots from `assets/`:
`app-obsidian-map.png`, `app-vault-capture.png`, `app-trade-log.png`, and
`app-trading-insights.png`.
