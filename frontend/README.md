# Cousin Eddie - Frontend Dashboard

Clean, modern web UI to showcase the alternative data platform.

## Features

- 📊 Real-time signal dashboard
- 🏢 Multi-company support
- 📈 Signal visualization (active + coming soon)
- 🎯 Category-based organization
- 📱 Responsive design

## Quick Start

### 1. Start the API Backend

```bash
# From project root
export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/cousin_eddie"
python api/main.py
```

API will run on `http://localhost:8000`

### 2. Open the Frontend

```bash
cd frontend
# Open index.html in browser or use a local server:
python -m http.server 8080
```

Then visit: `http://localhost:8080`

## Demo Mode

The frontend has fallback sample data if the API is not available. Perfect for:
- Showing friends the vision
- GitHub Pages hosting (static demo)
- Development without running backend

## Deployment

### Option 1: GitHub Pages (Static Demo)

1. Push `frontend/` directory to GitHub
2. Enable GitHub Pages in repo settings
3. Select `frontend/` as source
4. Visit `https://yourusername.github.io/cousin-eddie/`

**Note:** In demo mode (API offline), shows sample data.

### Option 2: Full Stack Deployment

**Backend:**
- Deploy FastAPI to Railway, Render, or Vercel
- Update `API_URL` in `app.js` to production URL

**Frontend:**
- Host on Vercel, Netlify, or GitHub Pages
- Update CORS settings in `api/main.py` for production

## Architecture

```
frontend/
├── index.html    # Main dashboard
├── style.css     # Modern dark theme
├── app.js        # API integration + demo data
└── README.md

api/
└── main.py       # FastAPI backend
```

## Customization

**Change API URL:**
Edit `app.js` line 2:
```javascript
const API_URL = 'https://your-api.com';
```

**Add more signal processors to demo:**
Edit `loadSampleProcessors()` in `app.js`

**Theme colors:**
Edit CSS variables in `:root` in `style.css`

## Screenshots

*Dashboard showing 7 active + 6 coming soon signal processors*

- Regulatory: Form 4, Financials, MD&A (+ 3 coming soon)
- Web/Digital: App ratings, Google Trends (+ 1 coming soon)
- Workforce: Job postings
- Alternative: Reddit sentiment (+ 2 coming soon)
