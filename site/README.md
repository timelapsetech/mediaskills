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

**Build must use GitHub Actions** (not “Deploy from a branch”) under **Settings → Pages → Build and deployment**.

### If deploy fails with “Deployment failed, try again later”

The Astro **build** usually succeeds; the **deploy** step fails when GitHub Pages cannot publish. Common causes:

1. **Custom domain added before the first successful deploy** — In **Settings → Pages**, temporarily clear the custom domain, re-run the workflow, confirm `https://timelapsetech.github.io/mediaskills/` works, then add `mediaskills.ai` back.
2. **DNS not pointed at GitHub Pages** — `mediaskills.ai` must resolve to GitHub, not only Cloudflare. Check with `dig mediaskills.ai +short`.
3. **Cloudflare proxy** — During initial setup, use **DNS only** (grey cloud) or point apex/www at GitHub correctly before enabling the orange proxy.

### Custom domain (`mediaskills.ai`)

Configure the domain in **Settings → Pages → Custom domain** (not via a `CNAME` file in this repo — workflow deploys ignore it).

At your DNS provider (Cloudflare example):

| Type | Name | Target | Proxy |
| --- | --- | --- | --- |
| `CNAME` | `www` | `timelapsetech.github.io` | DNS only until HTTPS works |
| `A` | `@` | `185.199.108.153` (and `.109`, `.110`, `.111`) | DNS only until HTTPS works |

Or apex `CNAME` flattening to `timelapsetech.github.io` if your DNS supports it.

After DNS propagates, enable **Enforce HTTPS** in Pages settings.

## Structure

| Path | Purpose |
| --- | --- |
| `scripts/sync-content.mjs` | Generates `catalog.json` from repo skills & workflows |
| `src/pages/` | Routes: home, skills, cookbooks, ops, install |
| `src/data/catalog.json` | Generated — do not edit by hand |
| `public/media/` | Sample fixtures copied at sync time |
