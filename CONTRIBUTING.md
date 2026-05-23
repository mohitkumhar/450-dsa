# Contributing to 450 DSA Tracker

First off, thank you for considering contributing to the 450 DSA Tracker! It's people like you that make the open-source community such an amazing place to learn, inspire, and create.

This document provides guidelines and instructions for contributing to this project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Environment Setup](#environment-setup)
4. [How to Contribute](#how-to-contribute)
    - [Reporting Bugs](#reporting-bugs)
    - [Suggesting Enhancements](#suggesting-enhancements)
    - [Pull Requests](#pull-requests)
5. [Development Guidelines](#development-guidelines)
6. [Commit Guidelines](#commit-guidelines)

## Code of Conduct

By participating in this project, you are expected to uphold a welcoming, inclusive, and harassment-free environment for everyone. Please read and follow the full [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/450-dsa.git
   ```
3. Navigate to the project directory:
   ```bash
   cd 450-dsa
   ```
4. Add the original repository as the `upstream` remote:
   ```bash
   git remote add upstream https://github.com/mohitkumhar/450-dsa.git
   ```

## Environment Setup

This project uses Python, Flask, Flask-Login, Flask-Bcrypt, Authlib, and MongoDB via PyMongo/Flask-PyMongo.

1. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application locally:**
   ```bash
   python run.py
   ```
   The application will be available at `http://localhost:5000`. On first request, the app seeds MongoDB from `data.json` if the `topic` collection is empty.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue on GitHub. Include the following information to help us resolve it quickly:
* A clear and descriptive title.
* Steps to reproduce the issue.
* Expected behavior vs. actual behavior.
* Screenshots, if applicable.
* Your operating system and browser version.

### Suggesting Enhancements

Have an idea for a new feature or improvement? We'd love to hear it! Open an issue on GitHub and provide:
* A clear and descriptive title.
* A detailed explanation of the proposed feature.
* Why this feature would be useful to most users.

### Pull Requests

Ready to write some code? Great!

1. Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```
2. Make your changes in the code.
3. Test your changes locally to ensure everything works as expected.
4. Commit your changes (see [Commit Guidelines](#commit-guidelines)).
5. Push your branch to your fork:
   ```bash
   git push origin your-branch-name
   ```
6. Open a Pull Request (PR) against the `main` branch of the original repository.
7. Describe your changes clearly in the PR description and reference any related issues (e.g., "Fixes #123").

## Development Guidelines

* **Application structure**: The Flask app now uses an app factory in `app/__init__.py` and blueprint route modules under `app/auth`, `app/tracker`, `app/profile`, `app/leaderboard`, and `app/search`.
* **Extensions**: Shared Flask extensions live in `app/extensions.py`. Import shared objects such as `db`, `bcrypt`, `login_manager`, and `oauth` from there instead of creating new instances.
* **Helpers and fetchers**: Reusable helpers live in `app/utils.py`, and external platform fetchers live in `app/platforms/fetchers.py`.
* **Templates**: We use Jinja2 and Bootstrap 4 for templates (located in the `templates/` folder). Try to keep the UI clean and responsive.
* **Database**: MongoDB is used for persistence. If you change data access patterns, keep blueprint imports pointed at `app.extensions` and avoid importing from `app/__init__.py` inside route modules.
* **Code Style**: Please follow standard Python conventions (PEP 8). Keep your code clean, readable, and well-commented where necessary.

## Commit Guidelines

We recommend writing clear and concise commit messages. A good commit message should be structured as follows:

* Use the present tense ("Add feature" not "Added feature").
* Capitalize the first letter.
* Keep the subject line under 50 characters.
* Reference issues and pull requests liberally.

Example:
```
Add bookmarking functionality to topics view

Fixes #42
```

---

Thank you for your contributions!
