# Deploying the GENIUS site

The whole public site is **one folder with no build step**: `site/`.
It is plain HTML, CSS and vanilla JS. No Node, no bundler, no framework, no backend.

```
site/                  ← this is the folder you deploy
├── index.html         the landing page
├── favicon.svg
├── robots.txt
├── 404.html
├── _redirects         Netlify / Cloudflare rules (ignored elsewhere, harmless)
└── console/
    ├── index.html     the lab console
    └── data.js        run data, produced by the lab
```

## Before you deploy

Regenerate the run data so the console isn't empty:

```bash
python3 lab/run_demo.py --live
```

That writes `site/console/data.js`. Commit it — it is a build output the site needs,
and there is no server to generate it at request time.

Preview exactly what you will ship:

```bash
python3 serve.py
```

`serve.py` serves `site/` as the web root, so local and production paths match.

---

## Drag and drop

### Netlify Drop — fastest, no account needed to preview
1. Open <https://app.netlify.com/drop>
2. Drag the **`site`** folder onto the page.
3. You get a live URL in a few seconds. Claim it with a free account to keep it and
   attach a custom domain.

`_redirects` is picked up automatically, so `/dashboard/*` forwards to `/console/*`
and unknown paths get the styled 404.

### Cloudflare Pages
1. <https://dash.cloudflare.com> → Workers & Pages → Create → Pages → **Upload assets**
2. Drag the **`site`** folder.
3. Build command: *(leave empty)* · Output directory: `/`

### Vercel
Drag-and-drop needs the CLI or a Git repo:

```bash
npm i -g vercel
cd site && vercel --prod
```

Framework preset: **Other**. Build command: empty. Output directory: `./`

### GitHub Pages
Push the repo, then Settings → Pages → Source: *Deploy from a branch* →
branch `main`, folder `/site` if you move it to `/docs`, or use an action.
Simplest path: copy `site/` to a `gh-pages` branch root.

---

## Lovable

**You cannot drag a folder onto Lovable and get a website** — Lovable is an AI app
builder, not a static-file host. It accepts dragged files only *into an existing
project's* file tree, which adds an asset; it does not publish a folder.

Every Lovable project is a **Vite + React** app with a build step, and its GitHub
importer expects a single root `package.json`, a working dev script, and Tailwind
configured. The hand-written `site/` folder meets none of that.

So the project ships a second, Lovable-ready copy of the same site: **`genius-web/`**.
Same design, same copy, rebuilt as React components with Tailwind tokens.

### Getting it into Lovable

`genius-web/` must be its **own repository** — Lovable rejects monorepos, and this
project's root has Python beside the web app.

1. **Push `genius-web/` as a standalone repo.** From inside that folder:

   ```bash
   git init && git add -A && git commit -m "GENIUS site"
   ```

   Create an empty repo on GitHub, then add it as the remote and push.

2. **Import it.** In Lovable: *New Project → Import from GitHub*, authorise the Lovable
   GitHub App for that repo, and select it.

3. **Verify it builds** in Lovable's preview. It builds clean locally (`npm run build`),
   so an import failure means a Lovable-side setting, not the code.

4. **Publish** from Lovable, and attach a custom domain in its settings.

### Editing it by prompt afterwards

All copy is in `src/data/content.ts`, separated from layout. That is what makes prompting
work well — "change the hero subheading" edits one string rather than rewriting a
component. `genius-web/README.md` has the full map of where to change what.

### Which folder should you actually use?

| | `site/` | `genius-web/` |
|---|---|---|
| Deploy method | Drag-and-drop | Git push → Lovable |
| Build step | None | `npm run build` |
| Edit by prompting | No | **Yes** |
| Dependencies | Zero | React, Vite, Tailwind |
| Load weight | ~40 KB | ~230 KB (57 KB gzipped) |

**Use `site/` if you just want it live** — Netlify Drop, under a minute, nothing to break.
**Use `genius-web/` if you want to keep editing it by prompting in Lovable.**

Both render the same page. Keep whichever you actually maintain, and delete the other
once you have chosen — two copies of the same site will drift apart.

---

## Custom domain

All four hosts above take a custom domain in the same shape: add the domain in the
host's dashboard, then at your registrar point

- apex (`genius.xyz`) → the host's A record or ALIAS/ANAME target
- `www` → CNAME to the host's target

TLS is issued automatically on all four. Set the apex as canonical and redirect `www`
to it (or the reverse — just pick one and be consistent).

## After deploying, check

- [ ] `/` loads and fonts render (Google Fonts is the only external request)
- [ ] `/console/` shows metrics, not the "No run data found" panel
- [ ] a nonsense path shows the styled 404
- [ ] mobile: no horizontal scrolling
- [ ] the pre-launch ticker and disclaimers are visible and current
- [ ] the response carries `Content-Security-Policy` and `X-Frame-Options` (from `_headers`)
- [ ] with Phantom installed: **Connect wallet** lists it, connecting shows the address,
      **Prove ownership** shows the full message in the wallet and returns "Verified ✓"

---

## GitHub → private repo → public site (the "launch without showing the code" path)

This is the recommended way to go live. The **site is public, the repository is private**.
Netlify, Vercel and Cloudflare Pages all deploy from private GitHub repos through their
GitHub app — visitors see the pages, never the repo, the Python lab, the docs or the tests.

### 1. Create the repo

On GitHub: **New repository** → name it (e.g. `genius`) → visibility **Private** →
leave "Add a README" **unchecked** → Create.

### 2. Upload by drag-and-drop

A clean, upload-ready copy is on your Desktop: **`GENIUS-upload/`** (and `GENIUS-upload.zip`
as a backup). It excludes `node_modules`, build output, generated lab output and OS files —
63 files, well under GitHub's 100-files-per-upload limit.

1. On the empty repo page click **uploading an existing file**
   (or later: **Add file → Upload files**).
2. Open `GENIUS-upload/` in Finder, select **everything inside it** (⌘A), and drag it onto
   the upload area. Drag the *contents*, not the folder itself, so files land at the root.
3. Wait for all files to list, write a commit message, **Commit changes**.
4. Check that `.gitignore` **and the `.github/` folder** arrived — some browsers skip
   dotfiles/dotfolders when dragging. If either is missing, use **Add file → Create new
   file** and paste the local contents (for the workflow, name the file
   `.github/workflows/daily-run.yml` — GitHub creates the folders from the path).
5. Once `.github/workflows/daily-run.yml` is in the repo, open the **Actions** tab, select
   **Daily lab run**, and press **Run workflow** once to confirm it works. From then on it
   runs itself every day at 00:15 UTC: tests, live data, commit, redeploy.

Alternative, three commands from inside `GENIUS-upload/` (needs `gh` installed and logged in):

```bash
git init && git add -A && git commit -m "GENIUS — initial import"
```
```bash
gh repo create genius --private --source=. --push
```

### 3. Connect a host

**Netlify (recommended, zero config — `netlify.toml` is already in the repo)**
Netlify → *Add new site → Import an existing project → GitHub* → authorise for the
private repo → select it. Netlify reads `netlify.toml`: publish `site/`, no build. Deploy.
Custom domain and HTTPS in *Domain management*.

**Vercel** — `vercel.json` is included. *Add New → Project → Import* the repo. Framework
"Other". Deploy.

**Cloudflare Pages** — *Create → Pages → Connect to Git*. Build command: empty.
Output directory: `site`.

Every push to the repo redeploys automatically on all three.

### What "not showing the code" really means — be precise about this

| | Visible to visitors? |
|---|---|
| The GitHub repository | **No** — it is private |
| The Python lab, tests, docs, cost/decision documents | **No** — never deployed |
| The rendered pages | Yes — that's the site |
| The site's HTML, CSS and JavaScript | **Yes, unavoidably** — a browser has to receive them to render the page. Anyone can "View Source". The React build is minified, but minified is not hidden. |

There is no way to serve a web page without sending its front-end code to the browser.
That is true of every website on earth. What you *can* control — and what this setup
does — is that nothing beyond the page itself (the lab, the reasoning, the roadmap, the
numbers behind the site) ever leaves the private repo. Never put a secret, API key or
anything sensitive in `site/` or `genius-web/`.

### Keeping your identity out of it

- Project files contain no username, machine name, email or home paths (scanned and
  confirmed: zero hits).
- Commits made through the GitHub web uploader are attributed to your **GitHub account**.
  If the account name is your real name and you want it hidden, use a handle instead — and
  note that a private repo hides commit history from the public anyway.
- If you commit from the terminal, git stamps your local name/email. Use a neutral identity
  inside the repo:

```bash
git config user.name "GENIUS" && git config user.email "genius@users.noreply.github.com"
```

- Netlify/Vercel deploy logs are private to your hosting account.
