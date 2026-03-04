# Fulcrum Setup Guide

This file explains how to run the Fulcrum project after cloning or pulling the repository.

The project has:

- a Python backend in `./fulcrum`
- a Next.js frontend in `./fulcrum/frontend`
- a shared Python virtual environment expected at `./.venv` from the repo root

## 1. Clone the repository

From the directory where you want the project:

```bash
git clone <your-repo-url>
cd Capstone
```

If you already cloned it earlier:

```bash
git pull
```

## 2. Create the Python virtual environment

Create the backend virtual environment at the repo root, not inside `fulcrum`.

From the repo root:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

## 3. Install backend dependencies

From the repo root:

```bash
./.venv/bin/pip install -r ./fulcrum/requirements.txt
```

This installs the backend packages used by the FastAPI service and ML pipeline.

## 4. Install frontend dependencies

From the repo root:

```bash
cd ./fulcrum/frontend
npm install
cd ../..
```

## 5. Start the backend

The backend must run before the frontend because the frontend `/api/models` proxy calls the Python API.

From the repo root:

```bash
cd ./fulcrum
../.venv/bin/python -m uvicorn api.predict:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Useful backend routes:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/models`
- `http://127.0.0.1:8000/docs`

## 6. Start the frontend

Open a second terminal.

From the repo root:

```bash
cd ./fulcrum/frontend
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

Useful frontend routes:

- `http://localhost:3000/`
- `http://localhost:3000/models`

## 7. Startup order

Always start services in this order:

1. Start the backend in `./fulcrum`
2. Start the frontend in `./fulcrum/frontend`

If the backend is not running, the frontend models page will not be able to load the model registry.

## 8. Current proxy behavior

The Next.js frontend uses a local proxy route:

- frontend route: `/api/models`
- backend target: `http://127.0.0.1:8000/models`

By default, it points to:

```text
http://127.0.0.1:8000
```

If needed later, you can change this with:

```text
NEXT_PUBLIC_FULCRUM_API_BASE
```

## 9. Quick run checklist

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
./.venv/bin/pip install -r ./fulcrum/requirements.txt
cd ./fulcrum/frontend
npm install
```

Then start backend in terminal 1:

```bash
cd ./fulcrum
../.venv/bin/python -m uvicorn api.predict:app --reload
```

Then start frontend in terminal 2:

```bash
cd ./fulcrum/frontend
npm run dev
```

## 10. Common issue

If you see errors about missing Python packages even after installing them, make sure you are using the project virtual environment and not a global Python installation.

Use this backend command exactly:

```bash
../.venv/bin/python -m uvicorn api.predict:app --reload
```

Do not rely on a global `uvicorn` binary if the packages were installed into `./.venv`.
