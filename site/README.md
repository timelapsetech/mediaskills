# mediaskills site

Static documentation site for [mediaskills.ai](https://mediaskills.ai), built with [Astro](https://astro.build).

## Development

```bash
cd site
npm install
npm run dev
```

Content is synced from the parent repo on `predev` / `prebuild`:

```bash
npm run sync   # reads skills/, docs/workflows/ → src/data/catalog.json
```

## Build

```bash
npm run build
npm run preview
```

## Deploy (GitHub Pages)

Pushes to `main`/`master` that touch `site/`, `skills/`, or `docs/workflows/` trigger [`.github/workflows/deploy-site.yml`](../.github/workflows/deploy-site.yml).

### Custom domain setup

1. In the GitHub repo: **Settings → Pages → Build and deployment** → Source: **GitHub Actions**
2. **Custom domain:** `mediaskills.ai` (CNAME file is in `public/CNAME`)
3. At your DNS provider, add:
   - `A` records → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - or `CNAME` `www` → `<user>.github.io` if using www subdomain
4. Enable **Enforce HTTPS** after DNS propagates

## Structure

| Path | Purpose |
| --- | --- |
| `scripts/sync-content.mjs` | Generates `catalog.json` from repo skills & workflows |
| `src/pages/` | Routes: home, skills, cookbooks, ops, install |
| `src/data/catalog.json` | Generated — do not edit by hand |
| `public/media/` | Sample fixtures copied at sync time |
