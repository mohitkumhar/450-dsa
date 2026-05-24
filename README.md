# 450 DSA Tracker

🌐 **Live Demo:** [https://450-ds.vercel.app](https://450-ds.vercel.app)

Track your progress through Love Babbar's 450 DSA problems — with platform sync, leaderboard, and more.

[![Open For PR](https://img.shields.io/badge/Open%20For-PR-orange?style=for-the-badge&logo=github)](https://github.com/mohitkumhar/450-dsa)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.3-black?style=flat&logo=flask)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-green?style=flat&logo=mongodb)

---

## What is this?

A full-stack Flask web app to help you track, manage, and share your DSA journey. Originally a React + LocalBase project, it's been completely rewritten in Python with MongoDB as the database.

---

## Features

- **Topic-wise tracking** — browse all 24 DSA topics and mark questions done
- **Bookmarks** — save questions for quick review
- **Notes** — write and save personal notes per question
- **Search** — full-text search with topic, difficulty, platform, and status filters
- **OAuth login** — sign in with GitHub or Google, or register with email/password
- **Platform sync** — connect LeetCode, GFG, GitHub, HackerRank, Coding Ninjas and pull your stats
- **Profile dashboard** — activity heatmap, rating chart, difficulty breakdown, badges
- **Leaderboard** — ranked by C-Score (composite score across all platforms)
- **Public profiles** — shareable profile cards
- **Admin panel** — manage users and content
- **Export notes** — download your notes as Markdown
- **Docker support** — run the whole app with one command

---

## Quick Start

### Option 1 — Local setup

**1. Clone and set up environment**
```bash
git clone https://github.com/mohitkumhar/450-dsa.git
cd 450-dsa
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# For development, linting, and tests
pip install -r requirements-dev.txt
```

**2. Configure environment variables**
```bash
cp .env.example .env   # macOS/Linux
copy .env.example .env  # Windows
```

Edit `.env` and fill in your values:
```env
SECRET_KEY=your-random-secret-key

# MongoDB — use Atlas (free) or local
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/dsa_tracker

# GitHub OAuth (optional)
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Google OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Cloudinary — for profile photo uploads (optional)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

**3. Run**
```bash
python run.py
```

Open `http://localhost:5000` in your browser. The app seeds all 450+ questions from `data.json` on first run.

---

### Option 2 — Docker

```bash
git clone https://github.com/mohitkumhar/450-dsa.git
cd 450-dsa
docker compose up
```

Open `http://localhost:5000`.

---

## Project Structure

```
450-dsa/
├── app/
│   ├── __init__.py          # App factory
│   ├── extensions.py        # Shared Flask extensions (db, bcrypt, limiter...)
│   ├── utils.py             # Helpers, search logic, leaderboard scoring
│   ├── auth/                # Login, register, OAuth (GitHub, Google)
│   ├── tracker/             # Topics, questions, bookmarks, notes
│   ├── profile/             # Profile page, platform sync, photo upload
│   ├── search/              # Search API with filters
│   ├── leaderboard/         # Leaderboard routes and API
│   ├── admin/               # Admin dashboard
│   ├── public/              # Public profile pages
│   ├── faq/                 # FAQ page
│   └── platforms/
│       └── fetchers.py      # LeetCode, GFG, GitHub, HackerRank, Coding Ninjas fetchers
├── templates/               # Jinja2 HTML templates
├── static/                  # CSS and JS assets
├── tests/                   # Pytest test suite
├── data.json                # All 450+ DSA questions
├── run.py                   # App entry point
├── requirements.txt         # Python dependencies
├── requirements-dev.txt     # Dev/test dependencies
├── .env.example             # Environment variable template
├── Dockerfile
└── docker-compose.yml
```

---

## Database

The app uses **MongoDB** (via Flask-PyMongo). There is no SQLite or SQLAlchemy — those were part of an earlier version.

**Collections:**
- `user` — user accounts, progress, platform usernames, external stats
- `topic` — DSA topic names and ordering
- `question` — all 450+ problems with URLs

MongoDB is accessed through `app.extensions.db` (a `LocalProxy` to `mongo.db`). All indexes are created on startup in `app/__init__.py`.

You can use [MongoDB Atlas](https://cloud.mongodb.com) (free M0 tier) or a local MongoDB instance.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard — all topics with progress |
| GET | `/topic/<id>` | Questions for a topic |
| GET | `/search` | Search page |
| GET | `/bookmarks` | Saved bookmarks |
| GET | `/profile` | User profile dashboard |
| GET | `/leaderboard` | Global leaderboard |
| GET | `/u/<user_id>` | Public profile |
| GET | `/api/search_questions` | Search API (supports `q`, `topic_id`, `difficulty`, `platform`, `status`, `limit`) |
| GET | `/api/leaderboard` | Leaderboard API (supports `mode`: cscore, questions, rating, college) |
| POST | `/update_question/<id>` | Update done/bookmark/notes for a question |
| POST | `/sync_platforms` | Sync external platform stats |
| POST | `/edit_profile` | Update profile fields |
| POST | `/upload_photo` | Upload profile photo |
| POST | `/delete_account` | Permanently delete account (GDPR) |
| GET | `/search_universities` | University autocomplete |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 2.3 |
| Database | MongoDB (Flask-PyMongo) |
| Auth | Flask-Login, Flask-Bcrypt, Authlib (OAuth) |
| Rate limiting | Flask-Limiter |
| Frontend | Jinja2, Bootstrap Icons, Chart.js |
| Photo storage | Cloudinary |
| Testing | Pytest |
| Deployment | Docker, Vercel |

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask session secret |
| `MONGO_URI` | Yes | MongoDB connection string |
| `GITHUB_CLIENT_ID` | No | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | No | GitHub OAuth app client secret |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth client secret |
| `CLOUDINARY_CLOUD_NAME` | No | Cloudinary cloud name for photo uploads |
| `CLOUDINARY_API_KEY` | No | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | No | Cloudinary API secret |

---

## Credits

- DSA problem set curated by **[Love Babbar](https://www.youtube.com/@LoveBabbar)** — [450 DSA Cracker Sheet](https://450dsa.com)
- Flask conversion and ongoing development by the open-source community

---

## Contributing

PRs are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening one.
