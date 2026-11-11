# ianadams.media

Repo: https://github.com/adamsian3/personal-site

Ian Adams' personal website, in the Fjord brand. The content lives in the Obsidian vault (`Ian Remote Vault/2 - Areas/Sites/IanAdams.media`); this folder turns it into a static site.

## Update the site

1. Edit the notes in Obsidian as usual.
2. Rebuild (or ask Claude to): `python3 build.py`
3. Push: `git add -A && git commit -m "Update site" && git push`

Cloudflare Pages publishes the `public/` folder on every push.

## How the vault maps to the site

| Vault note | Page |
|---|---|
| Home | `/` |
| About/About me | `/about/` |
| Blog/Tech & Media (+ posts) | `/Blog/TechMedia/` |
| Blog/Travel Blog (+ Travel Posts) | `/Blog/Travel/` |
| Blog/Newsletters | `/Blog/Newsletters/` (only issues linked from the index note are published) |
| About/Gaming | `/gaming/` |
| Links | `/Links/` |
| `pins/pins.json` (in this folder) | `/Pins/` |

- Posts keep the `permalink` from their frontmatter, so old Obsidian Publish links still work.
- `By Ian Adams`, `Date Posted`, `Location`, `Visited` and `Tags` lines become the post header.
- `![[image.jpg|300]]` embeds are resized to WebP in `public/img/`.
- Links to notes that aren't on the site become plain text.
- Em dashes are swapped for commas (or a colon in titles).

## Hosting (Cloudflare Pages)

Workers & Pages › Create › Pages › Connect to Git › `adamsian3/personal-site` repo. Build command: none. Output directory: `public`. Then add the custom domain `ianadams.media` under the project's Custom domains tab.
