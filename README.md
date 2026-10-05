# Shashank Adari — portfolio website

A professional portfolio for job applications and side projects, written in plain language for people who
aren't data engineers. Every role and project says what the problem was, what Shashank did and what changed,
with the technical details underneath for those who want them.

The site rebuilds itself every night: a small Python pipeline pulls GitHub activity, keeps a history, checks
the data and republishes to GitHub Pages. New blog posts are Markdown files.

| Page | What's on it |
|---|---|
| `/` | one scrolling page: hero with an interactive map of what I work with, results in numbers, About Me, Skills, Projects (click a card for the plain-language story and the technical details), Experience (click a role for the full story and its architecture drawing), Awards & Certificates, Work With Me, Contact |
| `/blog/` | notes and articles |
| `/activity/` | GitHub activity, updated nightly |
| `/playground/` | a read-only SQL console over the site's own data (for technical visitors) |

Dark theme by default; visitors can switch to light with the toggle.

---

## Run it on your computer

```bash
make setup      # once: creates .venv and installs the two dependencies
make refresh    # full pipeline: pulls GitHub data, then builds _site/
make serve      # open http://localhost:8000
```

`make build` re-renders from data already on disk (offline, under a second).

## Write a blog post

```bash
make note title="What I learned about Delta MERGE today" tags=delta,spark   # short note
make post title="How we proved 51 billion rows were correct" tags=migration  # longer article
```

That creates `content/posts/YYYY-MM-DD-slug.md` with the front matter filled in. Write, then push:

```bash
git add content/posts && git commit -m "post: ..." && git push
```

- **From a phone:** on github.com, open `content/posts/`, *Add file*, name it `2026-10-06-my-note.md`, paste the
  front matter from `_template.md`, commit. It's live in a few minutes.
- A post with a future `date:` publishes automatically on that morning. `draft: true` keeps it hidden.

## Change the words on the site

Everything comes from two files:

- `content/profile.json`: every sentence on the page: the story, roles, projects, services, numbers, FAQ,
  education, certifications, awards, and the nodes of the hero map (`graph`).
- `site.config.json`: name, email, links, whether you're taking projects, the résumé file, the form endpoint.

The build fails with a clear message if something is inconsistent (for example a tool listed in a role that
isn't in the skills catalog).

## The résumé

`static/resume/Shashank_Adari_Resume.pdf` is served as a download from the home, about and contact pages.
**It currently contains your phone number.** If you'd rather not publish that, export a version without it and
replace the file, or set `"resume_pdf": ""` in `site.config.json` to hide the button.

## Logo, photo and film

- **Logo** (`static/brand/`): the A-roof-over-wave mark from your logo kit, in dark and light versions. It's in the
  header, the footer, the browser tab (`static/favicon.svg`, `favicon-32.png`), the phone home-screen icon and as a
  faint watermark behind the Contact section. Replace the files with the same names to update it.
- **Photo** (`static/img/shashank-headshot.jpg`): the blazer headshot, used in the About section and at the centre of
  the hero map. It is the only photo on the site.
- **Film** (`static/video/`): the 30-second silent intro, 1080p for desktop, 720p for phones, and `poster.jpg`. It
  plays muted on a loop in its own panel under the hero, pauses when scrolled out of view, and shows the poster for
  visitors who have asked their device for less motion.

---

## Put it online (one time, about two minutes)

1. Create a **public** GitHub repository named **`adarishashank.github.io`**.
2. Push this folder:
   ```bash
   git init -b main
   git add .
   git commit -m "site: portfolio"
   git remote add origin https://github.com/adarishashank/adarishashank.github.io.git
   git push -u origin main
   ```
3. In the repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Wait for the *pipeline* workflow in the **Actions** tab to finish. The site is at `https://adarishashank.github.io/`.

From then on it rebuilds every night at 00:05 IST and whenever you push.

### Optional

| Want | Do |
|---|---|
| Receive form messages in your inbox instead of opening the visitor's email app | Create a free form at formspree.io and put its endpoint in `gigs.form_endpoint` |
| Pause project requests | Set `gigs.available` to `false` |
| Private GitHub contributions in the activity heatmap | Turn on *Include private contributions* in your GitHub profile settings, create a fine-grained token with no repository access, save it as the repo secret `GH_STATS_TOKEN` |
| Your own domain | Set `custom_domain` and `url` in `site.config.json`, then add the DNS records GitHub shows under Settings → Pages |

## Two things that would make the Projects page stronger

Both projects are described but not linked, because neither is public yet:

- Push **lakehouse-signoff** to `github.com/adarishashank/lakehouse-signoff` (the README says it's there, but
  the repository doesn't exist yet), then add `{"label": "Code on GitHub", "href": "..."}` to its `links` in
  `profile.json`.
- When **Pathfinder Stories** goes live, add its URL the same way.

## Layout

```text
content/            profile.json (all the words) + posts/*.md
pipeline/           run.py · ingest_github · transform · posts · quality · build_site · figures · figure_specs · new_post
templates/          base, index (the one-page portfolio), blog_index, post, activity, playground, 404
static/             css · js (site, app, charts, minisql, blog) · img · resume
site.config.json    name, links, settings
.github/workflows/  nightly build + deploy
```
