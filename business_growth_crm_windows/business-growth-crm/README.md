# Business Growth CRM — Windows LAN

## Install
1. Extract to `C:\BusinessGrowthCRM`.
2. Open PowerShell in that folder.
3. Run:
   ```powershell
   py -3 -m venv venv
   .\venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```
   If activation is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.
4. Edit `.env` and replace `SECRET_KEY` with a long random secret. API keys can remain blank.
5. Start with `waitress-serve --host=0.0.0.0 --port=5000 app:app` or run `run_crm.bat`.
6. On this PC visit `http://127.0.0.1:5000/setup` and create the admin account.
7. Run `ipconfig`; on another device on the same trusted Wi-Fi open `http://YOUR-PC-IP:5000`.

After installing this update, stop and restart the CRM once. It creates the Fact Finder table automatically; existing leads are not altered. To sanity-check the application from PowerShell, run `venv\Scripts\python.exe -B -c "import app; print('Fact Finder ready')"` (with the CRM stopped if its database is stored on a synced/network folder).

## Firewall
If another device cannot connect, add a Windows Defender Firewall inbound rule for TCP 5000, Private profile only. Do not enable Public profile or router port forwarding. Check that Wi-Fi client isolation is disabled.

## Modules
Login, lead database, pipeline stages, lead scoring, activity log, follow-ups, campaigns, CSV/XLSX import, XLSX export, optional Google Places prospect search, Fact Finder review queue, optional Groq message drafting, WhatsApp click-to-chat with manual sending.

## Fact Finder (permitted public-source data)
Fact Finder is deliberately an import-and-review workflow, not a web scraper. Export data only through a source's official API, permitted feed, licensed export, or a CSV you compiled manually. It does not log in, solve CAPTCHAs, bypass paywalls, or crawl Yellow Pages Kenya or any other directory.

1. Use the source according to its terms and export/save a CSV you are allowed to use.
2. In **Fact Finder**, enter the source name and its URL, then upload the CSV.
3. In **Fact Finder review**, inspect each source link and evidence snippet. Possible duplicates are matched first by normalized phone, then by business name.
4. Add a review note and select **Promote after verification**. Only then is a CRM lead created (or linked to its existing duplicate), with an activity record retaining the source evidence.

Supported CSV columns include `business_name`, `category`, `county`, `town`, `phone`, `email`, `website`, `source_url`, `evidence`, and `confidence` (0–100). The retrieval time is recorded when the CSV is imported. Blank website data remains `UNVERIFIED`; neither Fact Finder nor Groq treats it as evidence of no website.

## Manual WhatsApp outreach queue
Open a lead and choose **Prepare for approval**. The CRM can draft a message, but it never sends it. In **Outreach**, review and edit the message, confirm your consent/lawful-basis process, then approve it. The only WhatsApp action is a click-to-chat link that opens your own app; press Send yourself and then select **Mark sent after manual send**. Use **Record opt-out** immediately when requested—future queue approval is blocked for that lead.

## Optional Google Places
Enable Places API (New) in Google Cloud, configure billing, restrict the API key to Places API, then add `GOOGLE_PLACES_API_KEY=...` to `.env` and restart. Search currently returns up to 20 places. Missing website data remains UNVERIFIED and is not proof of no website.

## Optional Groq
Add `GROQ_API_KEY=...` to `.env`; without it, a local draft template is used.

## Import columns
`business_name` (or `business`/`name`), `category`, `county`, `town` (or `location`), `phone`, `email`, `website`, `source`.

## Safety and backups
WhatsApp links only prefill a message; you must review and press Send. Respect opt-outs and applicable Kenyan privacy/marketing rules. Stop the app and back up `instance\crm.db`. Never share `.env` or database backups publicly. This is for a trusted private LAN, not public hosting. Use a strong password and do not expose port 5000 to the internet.
