# ianadams.media: how to update and publish

This is the handover for any Claude session working on Ian's personal site.

## 1. Access the session needs (check this first)
A session can only update the site if it can reach both folders on Ian's Mac:

| Folder on the Mac | What it holds |
|---|---|
| `~/Documents/ianadams-media` (or all of `~/Documents`) | The site builder and git repo (github.com/adamsian3/personal-site) |
| `Ian Remote Vault` (Obsidian) | All site content, under `2 - Areas/Sites/IanAdams.media` |

- **Cowork or Claude app sessions:** the session must be linked to Ian's computer, and both folders must be connected. Use "Add folder" in the desktop app, or ask Claude to request access. If you only see the cloud workspace, or one folder is missing, the session can't build the site.
- **Claude Code in Terminal:** `cd ~/Documents/ianadams-media` and start Claude there. The vault path also needs to be readable.
- **Quick test:** `ls ~/Documents/ianadams-media/build.py` and `ls "<vault>/2 - Areas/Sites/IanAdams.media/Site guide.md"` should both succeed.

## 2. Publish an update
1. Edit the content in the vault (`2 - Areas/Sites/IanAdams.media`), not in `public/`.
2. Build: `cd ~/Documents/ianadams-media && python3 build.py`. This needs Python 3 with markdown, Pillow and PyYAML. It writes the whole site to `public/`.
3. Check the output. Put any preview files in `public/__*`, which is gitignored.
4. Push: `git add -A && git commit -m "Update site" && git push`.

Cloudflare Pages deploys `public/` on every push. There's no build command on Cloudflare, and the output directory is `public`. The site is live on ianadams.media within a minute or two.

Ian runs `git push` himself unless he says otherwise. Never handle, store or ask for GitHub tokens or passwords. If a session can't reach his keychain, it stops after the build and gives him the push command.

## 3. Where each page comes from
`Site guide.md` in the vault folder is the live map. In short:

- **Home** `/`: `Home.md`.
- **About** `/about/`: `About/About me.md`.
- **Links** `/Links/`: `Links.md`.
- **Travel** `/Blog/Travel/`:
  - The list comes from `Blog/Travel Blog.md`. In that note, `*Coming soon*` and `*Visited*` markers set the map pin type.
  - The posts are in `Blog/Travel Posts`. Their frontmatter `coords` (lat, lng) and `visited` (a list of dates) drive the map.
  - New posts use `3 - Resources/Templates/Template, Travel Blog Post.md`, which opens with a `> [!summary]` key takeaways callout.
- **Tech & Media** `/Blog/TechMedia/`: `Blog/Tech & Media` and its posts.
- **Newsletters** `/Blog/Newsletters/`: only issues linked from the index note go live.
- **Coffee** `/coffee/`: `About/Coffee/Coffee.md`, with the café map built from `About/Coffee/Cafes.md` (a markdown table).
- **Pins** `/Pins/`: `About/Pins/Pins.md` (a table), with photos in `About/Pins/attachments`.
- **Gaming** `/gaming/`: the layout comes from `gaming/body.html` through `build_gaming()` in `build.py`. Keep that hook. Keep `About/Gaming/Gaming.md` in sync with it.

How the build treats posts:
- Posts keep their frontmatter `permalink`.
- `![[image.jpg|300]]` embeds become WebP files in `public/img/`.
- Links to notes that aren't on the site become plain text.

## 4. Technical notes
- **Maps:** self-hosted Leaflet (`assets/vendor/leaflet/`) and OpenStreetMap tiles with a grayscale CSS filter. No API keys.
- **Brand:** Fjord. The tokens are in `assets/style.css`. The stylesheet is cache-busted with `style.css?v=<md5>`.
- **Lightbox:** post images open bigger on tap (`article.prose img`).
- **Python version:** `build.py` must run on Python 3.10, so don't put backslashes inside f-string expressions.
- **Edit the real files:** always edit the current `build.py` on the Mac. Never overwrite it from an older copy. Doing that once rolled back the gaming page.

## 5. House rules
- Never use em dashes. Use commas, full stops, colons or parentheses instead.
- Only use Ian's own words and facts already in his notes. Don't invent descriptive phrases. If content is missing, ask him one question at a time.
- Follow the vault rules in the vault's `CLAUDE.md`:
  - Never delete. Move files to `Claude recommends to delete file`.
  - Ask before using templates. (The travel post template is pre-approved for new travel posts.)
  - Avoid creating new tags.
