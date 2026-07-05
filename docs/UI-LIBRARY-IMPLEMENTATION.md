# UI Library Implementation

## Summary

Quant Labs now uses an owned, shadcn-style UI foundation for app primitives and a small animated layer for polished shell elements. The implementation keeps the trading workspace focused and avoids registry-generated demo code.

## Libraries Added

- `class-variance-authority`: variant management for primitives like `Button` and `Badge`.
- `tailwind-merge`: conflict-safe class composition through `cn()`.
- `@radix-ui/react-slot`: `asChild` composition support for button-like primitives.
- `framer-motion`: restrained, accessible reveal animation for app-shell surfaces.

Lucide React was already present and remains the icon system.

## shadcn/ui Configuration

`apps/web/components.json` configures shadcn-style ownership for the Next.js app:

- `style`: `new-york`
- `tsx`: enabled
- `rsc`: enabled
- Tailwind config: `apps/web/tailwind.config.ts`
- Tailwind CSS entry: `apps/web/src/app/globals.css`
- aliases:
  - `@/components`
  - `@/components/ui`
  - `@/lib`
  - `@/lib/utils`

Primitives live in `apps/web/src/components/ui` and should stay focused on reusable app UI:

- `button.tsx`
- `badge.tsx`
- `card.tsx`
- `input.tsx`
- `label.tsx`
- `separator.tsx`
- `tabs.tsx`

## Tailwind And Theme Tokens

Tailwind now uses CSS variables for shadcn-compatible tokens and the existing Quant Labs palette:

- shadcn tokens: `background`, `foreground`, `card`, `primary`, `secondary`, `muted`, `accent`, `destructive`, `border`, `input`, `ring`
- product tokens: `ink`, `paper`, `line`, `moss`, `copper`, `signal`, `caution`, `loss`

Tokens are defined in `apps/web/src/app/globals.css` under `:root` and `.dark`. The app supports class-based dark mode through Tailwind `darkMode: ["class"]`.

Use `ThemeToggle` from `apps/web/src/components/shell/ThemeToggle.tsx` when a screen needs a theme switch. It stores the choice in `localStorage` and toggles the root `dark` class.

## Animated Components

Animated and special-effect components live separately in `apps/web/src/components/magic`:

- `animated-grid-pattern.tsx`: subtle app-shell grid background.
- `reveal.tsx`: Framer Motion reveal wrapper that respects reduced-motion preferences.
- `shine-card.tsx`: quiet animated top-border treatment used for metric tiles.

Keep these components away from core form/table primitives. Use them for shell, hero, empty states, and important summary cards only.

## Product Integration

The main app shell now uses:

- `DashboardHeader` for the compact hero/header surface.
- `ThemeToggle` for light/dark mode.
- shadcn-style `Badge`, `Button`, `Input`, and `Tabs` in important workspace controls.
- `ShineCard` for metric tiles.

The trading workspace behavior is preserved: vault capture, journal, trade log, insights, map, local storage, JSON import/export, and API health checks still work as before.

## Adding Components Later

Prefer copy-owned shadcn-style components over black-box UI packages.

1. Add the component under `apps/web/src/components/ui`.
2. Use `cn()` from `apps/web/src/lib/utils.ts`.
3. Use CSS variables from `globals.css` instead of raw hex colors.
4. Keep variants explicit with `class-variance-authority` when a component has real state.
5. Add animation only when it clarifies hierarchy or feedback.
6. Place Magic UI / Aceternity-inspired components under `apps/web/src/components/magic`.

## Guidance For Codex And Claude

- Use `components/ui` for primitives and repeated app controls.
- Use `components/magic` for animated shell or special visual treatments.
- Do not paste external demos directly into product screens.
- Do not add overlapping UI libraries for the same purpose.
- Keep serious dashboard screens restrained, dense, and scannable.
- Preserve accessibility: labels, roles, visible focus, reduced-motion behavior, and keyboard access.

## Verification

Commands run:

```bash
npm --prefix apps/web install
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
uv run --directory services/api pytest
```

Results:

- Web install: up to date
- Web lint: passed
- Web typecheck: passed
- Web build: passed
- API tests: 2 passed, 1 upstream deprecation warning from Starlette/FastAPI test client
