# Mosaic Memory web app

The Next.js interface presents local activity, source consent, privacy controls, and evidence-backed retrieval.

## Development

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`. The default API endpoint is `http://127.0.0.1:8000/api/v1`; override it with `NEXT_PUBLIC_API_BASE_URL` when needed.

## Checks

```powershell
npm run lint
npm run build
```

The app is configured with Next.js standalone output for the root Docker Compose deployment. See [`../README.md`](../README.md) for the full local setup.
