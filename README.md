# Prokerala Astrology Dashboard

This project hosts a minimal Next.js application that can be deployed to Vercel. It fetches real natal chart
and transit data from the [Prokerala Astrology API](https://api.prokerala.com/) based on birth details and
summarises the results using OpenAI first, falling back to DeepSeek if required.

## Getting started locally

1. Install dependencies:

   ```bash
   npm install
   ```

2. Create an `.env.local` file with the required secrets:

   ```bash
   PROKERALA_CLIENT_ID=your_client_id
   PROKERALA_CLIENT_SECRET=your_client_secret
   OPENAI_API_KEY=sk-...
   DEEPSEEK_API_KEY=sk-...
   ```

   OpenAI and DeepSeek keys are optional, but the AI insight will only show when at least one is configured.

3. Run the development server:

   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000) and submit your birth details to view the raw payloads and
   generated insight.

## Deploying to Vercel

### One-click deploy from GitHub (recommended)

1. Create a new Vercel project and import this repository.
2. In Vercel, copy the `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` values from the project settings.
3. In your GitHub repository settings, create the following Action secrets:
   - `VERCEL_TOKEN` – a [Vercel token](https://vercel.com/account/tokens) with deploy permissions.
   - `VERCEL_ORG_ID` – copied in step 2.
   - `VERCEL_PROJECT_ID` – copied in step 2.
   - `PROKERALA_CLIENT_ID`
   - `PROKERALA_CLIENT_SECRET`
   - `OPENAI_API_KEY` (optional)
   - `DEEPSEEK_API_KEY` (optional)
4. Push to `main` (or trigger the workflow manually) to run the **Deploy to Vercel** GitHub Action. The workflow
   builds the Next.js app and publishes it to production. Once complete, Vercel assigns a `vercel.app` URL that you
   can share immediately.

### Manual deploy via Vercel dashboard

1. Create or import the project on Vercel.
2. Set the same environment variables as secrets in the Vercel dashboard (Project Settings → Environment Variables).
3. Trigger a deploy. Vercel will run `npm install` and `npm run build` automatically. Once the deployment is live,
   open the provided `vercel.app` URL to access the dashboard.

## Notes

- The API route caches the OAuth token until expiry to reduce token requests across invocations.
- Raw natal chart and transit data are returned to the browser so you can archive or inspect them as needed.
- The AI prompt includes both natal and transit summaries to keep responses grounded in the fetched data.
