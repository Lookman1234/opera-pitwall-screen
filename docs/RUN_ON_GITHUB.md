# Running the real data on GitHub (about 15 minutes of your time, then waiting)

*Plain-language header: GitHub's computers download the NASA data with your free login and run the pipeline. You press one button. Nothing is installed on your computer.*

You need: a GitHub account, a NASA Earthdata account (https://urs.earthdata.nasa.gov/users/new), and this project uploaded to GitHub (see docs/PUBLISH_GUIDE.md).

## 1. Store your NASA login as secrets (5 min)

1. Open your project page on GitHub. Click **Settings** (top tab) > **Secrets and variables** > **Actions**.
2. Click **New repository secret**. Name: `EARTHDATA_USERNAME`. Secret: your Earthdata username. Click **Add secret**.
3. Again: Name `EARTHDATA_PASSWORD`, Secret: your Earthdata password.

4. Again: Name `PITWALL_EXCLUDE`, Secret: the comma-separated list in your private file `config/exclude.local.yaml` (I will give you the exact text to paste). This keeps the employer exclusion active on GitHub without the name appearing anywhere public.

Secrets are hidden: nobody, including me, can read them back. They are only handed to the download step.

## 2. Allow NASA's data archive to be used by your login (2 min)

1. Log in at https://urs.earthdata.nasa.gov. Click **Applications > Authorized Apps**.
2. Click **Approve More Applications**, search **ASF**, and approve "Alaska Satellite Facility Data Access". (If downloads later fail with "unauthorized", this approval is usually the missing piece.)

## 3. Press Run (1 min)

1. Click the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Run pipeline** on the left > **Run workflow** (right) > green **Run workflow**.
3. A yellow dot appears. It turns into a green tick when finished (minutes to a few hours, depending on how many maps there are). A red cross means something failed: send me a screenshot of the red step.

## 4. Get the results (2 min)

Click the finished run, scroll to **Artifacts**, click **pipeline-results** to download a zip. Upload that zip to this chat.
