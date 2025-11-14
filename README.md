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

1. Create a new Vercel project and import this repository.
2. Set the following environment variables in the Vercel dashboard (Project Settings → Environment Variables):
   - `PROKERALA_CLIENT_ID`
   - `PROKERALA_CLIENT_SECRET`
   - `OPENAI_API_KEY` (optional)
   - `DEEPSEEK_API_KEY` (optional)
3. Trigger a deploy. Vercel will run `npm install` and `npm run build` automatically. Once the deployment is live,
   open the provided `vercel.app` URL to access the dashboard.

## Notes

- The API route caches the OAuth token until expiry to reduce token requests across invocations.
- Raw natal chart and transit data are returned to the browser so you can archive or inspect them as needed.
- The AI prompt includes both natal and transit summaries to keep responses grounded in the fetched data.
