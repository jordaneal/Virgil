# virgildm.com — Operations Doc

Landing page for **Virgil's Hearth**, a persistent D&D campaign run on Discord.
Related to the broader Virgil project (Discord bot in `/home/jordaneal/scripts/`,
docs in `/home/jordaneal/virgil-docs/`). This is a **static site, no backend**.

## Where things live

| Path | What |
|---|---|
| `/var/www/virgildm/` | All served files (this directory) |
| `/var/www/virgildm/index.html` | The entire site — ~1.96MB self-unpacking Claude artifact |
| `/var/www/virgildm/favicon.svg` | Gold flame on dark, brand colors |
| `/var/www/virgildm/og.png` | 1200×630 social preview (rendered from og.svg) |
| `/var/www/virgildm/og.svg` | Source for og.png — edit this, re-render |
| `/var/www/virgildm/robots.txt` | Allow all + sitemap pointer |
| `/var/www/virgildm/sitemap.xml` | Single URL: the homepage |
| `/var/www/virgildm/index.html.bak.*` | Timestamped backups from previous patches |
| `/etc/nginx/sites-available/virgildm` | Nginx server block (symlinked from sites-enabled) |
| `/etc/sysctl.d/99-nonlocal-bind.conf` | `ip_nonlocal_bind=1` — boot-race fix (see below) |
| `/etc/systemd/system/cloudflared.service` | Tunnel service (token-based, no config file) |

## How traffic flows

- **Public:** Cloudflare → cloudflared tunnel → `127.0.0.1:80` (nginx) → files
- **Tailnet:** Tailscale Funnel (`https://virgil-server.tail09bf1c.ts.net`) → `100.122.110.119:80` (nginx) → same files
- Nginx listens on both `127.0.0.1:80` and `100.122.110.119:80`. No public bind on port 80, no port 443 on this host (Cloudflare terminates TLS).

## What index.html actually is

A self-contained Claude artifact bundle. Structure (top to bottom):

1. **Outer head:** `<title>`, meta tags (description/OG/Twitter/favicon — added post-deploy, see "patches" below), inline `<style>` for the unpacker UI.
2. **Inline unpacker script** (~lines 70-205): on `DOMContentLoaded`, decodes the manifest, builds Blob URLs, swaps the document.
3. **`<script type="__bundler/manifest">`** (line 207, ~1.9MB): JSON keyed by UUID, each value `{mime, compressed, data}` where `data` is gzip+base64.
4. **`<script type="__bundler/ext_resources">`**: empty `[]` here, unused.
5. **`<script type="__bundler/template">`**: stringified HTML doc that references the UUIDs as relative URLs.

Runtime: decode manifest → make Blob URLs → splice them into the template → `DOMParser` + `document.documentElement.replaceWith(...)` swaps the entire document. From there a React 18 app renders into `#root`.

**36 bundled assets:** 14 text/babel components (`App`, `Hero`, `Nav`, `LivingWorld`, `Path`, `Session`, `Codex`, `Calling`, `Library`, `Resources`, `Hearth`, `Footer`, `Lantern`, `Sigil`), React + ReactDOM + Babel-standalone (the three biggest), 14 woff2 fonts (Cormorant Garamond + JetBrains Mono variants).

## Editing the site

The React app source lives inside the manifest as gzip+base64. To change content:

- **Easy way:** regenerate the artifact in Claude.ai with new instructions, then replace `/var/www/virgildm/index.html` with the new file. **You will need to re-apply the patches below** — they live inline in the unpacker script.
- **Hard way:** decode the relevant manifest entry, edit the JS, re-encode, splice back. Brittle.

**Outer-head meta tags survive an artifact regeneration** only if you re-run the polish patch. They're not part of the Claude artifact.

After replacing `index.html`: Cloudflare doesn't cache (`cf-cache-status: DYNAMIC`), browsers revalidate (`Cache-Control: no-cache`), so updates appear on next page load.

## Custom patches applied to the live HTML

These are NOT in any source-of-truth Claude artifact. If you regenerate, you must re-apply.

### 1. Bundler error toast filter

**Why:** the unpacker installed a `window.addEventListener('error', ...)` toast that caught third-party errors. Specifically, Cloudflare's Bot Fight Mode injects a script that creates an iframe attached to `document.body`, then accesses `iframe.contentWindow.document` from a deferred callback. Our bundler `replaceWith`s the document, detaching CF's iframe — the deferred call null-derefs. Cosmetic, but ugly.

**Patch:** filter the toast to only fire on errors from `blob:` URLs (our own bundled assets). Lives inline near the unpacker (~line 75-90 of index.html, in the `window.addEventListener('error', ...)` block).

### 2. Outer-head meta tags

**Why:** the Claude artifact's outer head only had `<title>`. Crawlers and link-preview bots (Discord, Slack, iMessage) need OG / description / Twitter Card to render previews.

**Patch:** inserts description, theme-color, favicon link, full Open Graph set, Twitter Card, canonical — between `<title>` and `<style>` in the outer head.

Both patches were one-shot Python scripts. If you need to re-apply, recreate them based on the live `<head>` content (the previous scripts may be gone from `/tmp/`).

## Known production gotchas

### Boot race: nginx vs tailscaled

nginx binds `100.122.110.119:80` (the Tailscale interface IP). At boot, nginx can start before tailscaled brings up that IP, so nginx fails with `Cannot assign requested address` and stays dead until manually restarted.

**Fix in place:** `net.ipv4.ip_nonlocal_bind=1` (`/etc/sysctl.d/99-nonlocal-bind.conf`). Kernel-wide permission to bind to addresses not yet on an interface.

**Symptom if it recurs:** `systemctl status nginx` shows failed; cloudflared logs (`journalctl -u cloudflared`) say "connection refused on 127.0.0.1:80".

### Cloudflare Bot Fight Mode injects a buggy script

CF prepends an inline `<script>` before `</body>` that's incompatible with our document-swap. Cosmetic-only — the page renders fine. Filtered by patch #1 above. Do NOT disable Bot Fight Mode just because of this; the patch handles it.

### Mobile browsers cache HTML

We set `Cache-Control: no-cache` so they revalidate on every visit (cheap — returns 304 when unchanged). But if a mobile browser already has a cached copy from before that header existed, it may need ONE incognito hit to bust it.

## Common operations

```bash
# Health check (run all four)
systemctl is-active nginx cloudflared
curl -I https://virgildm.com/                  # expect HTTP/2 200, Cache-Control: no-cache
curl -I https://virgildm.com/og.png            # expect HTTP/2 200, image/png
curl -I http://127.0.0.1/                      # origin healthy

# Reload nginx after editing /etc/nginx/sites-available/virgildm
sudo nginx -t && sudo systemctl reload nginx

# Deploy a new artifact bundle
sudo cp -p /var/www/virgildm/index.html /var/www/virgildm/index.html.bak.$(date +%Y%m%d_%H%M%S)
sudo install -o www-data -g www-data -m 644 /path/to/new/index.html /var/www/virgildm/index.html
# Then re-apply patches #1 and #2 above.

# Regenerate og.png after editing og.svg
sudo rsvg-convert -w 1200 -h 630 -f png -o /var/www/virgildm/og.png /var/www/virgildm/og.svg

# Inspect public-facing meta tags
curl -sS https://virgildm.com/ | grep -oE '<meta [^>]+>' | head -20

# Decode the bundle manifest (Python)
python3 -c "
import json, base64, gzip, re
html = open('/var/www/virgildm/index.html').read()
m = re.search(r'<script type=\"__bundler/manifest\">\s*(\{.*?\})\s*</script>', html, re.DOTALL)
manifest = json.loads(m.group(1))
print(f'{len(manifest)} assets')
"
```

## Brand colors (for OG/favicon edits)

- Background dark: `#0E1116`
- Deep dark: `#06080C`
- Gold (accent): `#D4A648`
- Parchment (cream text): `#F4EBD3`
- Mist (dim blue secondary): `#7A92B8`
- Frame gradient: `#C9A158` → `#8C6A30` → `#5E4520`
- Flame gradient: `#FFF1B8` → `#FFD06A` → `#E8843A` → `#A03A1A`

Fonts (bundled in the artifact, not external): Cormorant Garamond (display, italic), JetBrains Mono (eyebrows / labels with letter-spacing).
