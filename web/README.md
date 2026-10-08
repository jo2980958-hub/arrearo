# Arrearo dashboard

React + Vite + TypeScript. Hash-routed, so `dist/` works on S3/CloudFront with no rewrite rules.

    npm install
    npm run dev                 # live API (needs .env.local, see .env.example)
    VITE_DEMO=1 npm run dev     # seeded demo data, no API or login
    npm run build               # -> dist/

Env vars (baked in at build time): VITE_API_URL, VITE_COGNITO_REGION, VITE_COGNITO_CLIENT_ID,
VITE_DEMO (1 = demo data), VITE_DEV_TOKEN (optional static JWT for dev).
