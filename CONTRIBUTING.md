# Contributing to 450 DSA Tracker

Thanks for taking the time to contribute! Whether it's a bug fix, new feature, or a docs improvement — all contributions are welcome.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Environment Setup](#environment-setup)
4. [MongoDB Setup](#mongodb-setup)
5. [Project Structure](#project-structure)
6. [How to Contribute](#how-to-contribute)
7. [Development Guidelines](#development-guidelines)
8. [Running Tests](#running-tests)
9. [Commit Guidelines](#commit-guidelines)

---

## Code of Conduct

By participating in this project, you agree to uphold a welcoming and harassment-free environment. Please read the full [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/450-dsa.git
   cd 450-dsa
   ```
3. Add the upstream remote so you can stay in sync:
   ```bash
   git remote add upstream https://github.com/mohitkumhar/450-dsa.git
   ```

---

## Environment Setup

This project uses **Python**, **Flask**, **Flask-PyMongo**, **Flask-Login**, **Flask-Bcrypt**, **Authlib**, and **Flask-Limiter**.

> There is no SQLAlchemy or SQLite in this project. The database is MongoDB.

**1. Create a virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

**2. Install dependencies**
```bash
# Runtime-only install
pip install -r requirements.txt

# Development, linting, and test install
pip install -r requirements-dev.txt
```

**3. Set up environment variables**
```bash
cp .env.example .env   # macOS/Linux
copy .env.example .env  # Windows
```

Edit `.env` with your values:
```env
SECRET_KEY=any-random-string

# MongoDB connection string (see MongoDB Setup below)
MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/dsa_tracker

# GitHub OAuth (optional — needed only for GitHub login)
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Google OAuth (optional — needed only for Google login)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Cloudinary (optional — needed only for profile photo uploads)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

**4. Run the app**
```bash
python run.py
```

Open `http://localhost:5000`. On the first request, the app automatically seeds all 450+ questions from `data.json` into MongoDB if the `topic` collection is empty.

---

## MongoDB Setup

The app requires a running MongoDB instance. You have two options:

### Option A — MongoDB Atlas (recommended, free)

1. Go to [https://cloud.mongodb.com](https://cloud.mongodb.com) and create a free account
2. Create a free **M0** cluster
3. Under **Database Access**, create a user with a username and password
4. Under **Network Access**, click **Add IP Address → Allow Access from Anywhere**
5. Click **Connect → Drivers** and copy the connection string
6. Paste it into your `.env` as `MONGO_URI`, replacing `<password>` with your actual password

### Option B — Local MongoDB

1. Install [MongoDB Community Server](https://www.mongodb.com/try/download/community)
2. Start the service:
   ```bash
   # Windows
   net start MongoDB

   # macOS/Linux
   mongod
   ```
3. Set in `.env`:
   ```env
   MONGO_URI=mongodb://localhost:27017/dsa_tracker
   ```

---

## Project Structure

```
450-dsa/
├── app/
│   ├── __init__.py          # App factory — initializes extensions and blueprints
│   ├── extensions.py        # Shared extensions: db, bcrypt, login_manager, limiter, oauth
│   ├── utils.py             # Helpers: search logic, leaderboard scoring, platform utils
│   ├── auth/                # Login, register, logout, OAuth (GitHub, Google)
│   ├── tracker/             # Topics, questions, bookmarks, notes export
│   ├── profile/             # Profile page, platform sync, photo upload
│   ├── search/              # Search page and /api/search_questions
│   ├── leaderboard/         # Leaderboard page and /api/leaderboard
│   ├── admin/               # Admin dashboard
│   ├── public/              # Public profile pages
│   ├── faq/                 # FAQ page
│   └── platforms/
│       └── fetchers.py      # External platform data fetchers
├── templates/               # Jinja2 HTML templates
├── static/                  # CSS and JS assets
├── tests/                   # Pytest test suite
├── data.json                # All 450+ DSA questions (seeded on first run)
├── run.py                   # Entry point
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

**Key things to know:**
- All shared Flask extensions live in `app/extensions.py` — import `db`, `bcrypt`, `login_manager`, `limiter`, `oauth` from there
- Routes are split into blueprints under `app/` — don't add routes directly to `app/__init__.py`
- MongoDB is accessed via `db` from `app.extensions` — it's a `LocalProxy` to `mongo.db`
- Platform data fetchers (LeetCode, GFG, GitHub, etc.) live in `app/platforms/fetchers.py`
- Reusable helpers and search/scoring logic live in `app/utils.py`

---

## How to Contribute

### Reporting Bugs

Open a GitHub issue and include:
- Clear title and description
- Steps to reproduce
- Expected vs actual behaviour
- OS, browser, and Python version if relevant
- Screenshots if helpful

### Suggesting Features

Open a GitHub issue with:
- What you want and why
- Any implementation ideas you have

### Pull Requests

1. Sync your fork with upstream before starting:
   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```
2. Create a branch:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   # or
   git checkout -b docs/your-doc-update
   ```
3. Make your changes and test locally
4. Commit (see [Commit Guidelines](#commit-guidelines))
5. Push and open a PR against `mohitkumhar:main`
6. Reference the related issue in your PR description (e.g. `Fixes #42`)

---

## Development Guidelines

- **Database**: This project uses **MongoDB** via Flask-PyMongo. There is no SQLAlchemy or SQLite. If you're changing data access patterns, use `db` from `app.extensions` and keep queries inside blueprint route files
- **Adding a new blueprint**: Create a folder under `app/`, add `__init__.py` and `routes.py`, then register it in `app/__init__.py`
- **Templates**: Jinja2 with Bootstrap Icons. Keep UI responsive and consistent with the existing dark theme
- **Auth**: Use `@login_required` from Flask-Login for protected routes. For admin routes, use the `@admin_required` decorator from `app/decorators/admin.py`
- **Rate limiting**: Use `@limiter.limit(...)` from `app.extensions` on heavy API endpoints
- **Code style**: Follow PEP 8. Keep functions small and focused. Add docstrings to non-obvious functions

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests live in the `tests/` folder and use `mongomock` so no real MongoDB connection is needed to run them.

---

## Commit Guidelines

Use clear, present-tense commit messages with a conventional prefix:

```
feat: add platform filter to search API
fix: handle missing user_doc in delete_account
docs: update CONTRIBUTING with MongoDB setup
refactor: extract leaderboard scoring to utils
test: add tests for search filters
```

- Keep the subject line under 72 characters
- Reference issues where relevant: `Fixes #42`
- One logical change per commit

---

Thanks for contributing! 🙌
