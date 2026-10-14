# Publish guide: v0.1.0

*Plain-language header: the steps to get this release onto GitHub and give it a permanent DOI. Pick Route A or B for GitHub, then do Zenodo.*

## Copy-ready text

- **Repository name:** `opera-pitwall-screen`
- **Description:** `Can NASA's open OPERA InSAR product screen open-pit walls? Reproducible validation pipeline (DISP-S1, 30 m).`
- **Release tag:** `v0.1.0`
- **Release title:** `v0.1.0: pipeline and synthetic tests (no real-data results yet)`
- **Release notes:**
  > First public release of OPERA Pit-Wall Screen: a reproducible pipeline that tests NASA OPERA DISP-S1 InSAR against documented open-pit wall failures. Includes the full pipeline, automatic wall outlines from Copernicus GLO-30, synthetic-pit tests with known answers, a one-button GitHub runner for real data, and documentation. No real-data results are included in this release. Author: Lukman Alabede (Independent Researcher), ORCID 0009-0008-7769-7455.
- **Topics:** `insar`, `opera`, `sentinel-1`, `open-pit-mining`, `slope-stability`, `remote-sensing`

## GitHub, Route A (recommended, 5 min): let Claude push it

This keeps the full version history, and future updates are one message.
1. Make sure the empty repository exists: https://github.com/new, name `opera-pitwall-screen`, **Public**, with nothing ticked under "Initialize". Click **Create repository**.
2. Give Claude access: in Claude, open **Settings > Connectors**, find **GitHub**, and click **Connect** (or **Configure**). On the GitHub page that opens, choose **Only select repositories**, pick `opera-pitwall-screen`, and click **Install** (or **Save**).
3. Reply "connected" in the chat. Claude pushes the code and the `v0.1.0` tag.

## GitHub, Route B (10 min): upload it yourself in the browser

1. Create the empty repository as in Route A, step 1.
2. Unzip `opera-pitwall-screen-v0.1.0.zip` on your computer.
3. On the new repository page, click **uploading an existing file**. Open the unzipped folder, select everything inside it (including the `.github` folder; on a Mac press Cmd+Shift+. to show hidden files), and drag it onto the page.
4. In "Commit changes", type `v0.1.0 release` and click **Commit changes**.
5. Click **Releases > Create a new release**. Under **Choose a tag**, type `v0.1.0` and click **Create new tag**. Paste the title and notes from above. Click **Publish release**.

## Zenodo DOI (5 min, after GitHub)

Do this **before** creating the GitHub release in Route B, or ask Claude to re-tag in Route A, because Zenodo only archives releases made after it is switched on.
1. Log in at https://zenodo.org (use **Log in with GitHub** or ORCID).
2. Go to https://zenodo.org/account/settings/github/. Click **Sync now** if the repository is not listed.
3. Flip the switch next to `Lookman1234/opera-pitwall-screen` to **On**.
4. Create (or re-create) the `v0.1.0` release on GitHub. Within a few minutes Zenodo shows a new record with a DOI like `10.5281/zenodo.1234567`.
5. Send the DOI to Claude. It goes into the README and CITATION.cff as v0.1.1, and into your evidence log.

## Then: the first real-data run
Follow `docs/RUN_ON_GITHUB.md`. For the `PITWALL_EXCLUDE` secret, paste the one-line list Claude sent you in the chat. It is deliberately not written anywhere in this public project.
