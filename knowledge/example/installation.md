# Atlas — Installation Guide

## System Requirements

Atlas requires Python 3.12 or newer. The application runs entirely locally and
does not require any paid API keys. Ollama must be installed to provide the LLM
and embeddings. A minimum of 8 GB of RAM is recommended for the default models.

## Supported Operating Systems

Atlas supports macOS and Linux. Windows is supported through Docker Desktop
using the containerized deployment described in the deployment guide.

## Install the application

1. Clone the repository.
2. Copy `.env.example` to `.env`.
3. Install dependencies with `uv sync`.
4. Start the backend server with `uv run uvicorn app.main:app`.
5. Start the development frontend with `npm run dev`.

## Start Ollama

Ollama must be running before Atlas starts. Run `ollama serve`, then verify the
health endpoint. The default configuration uses the gemma2 model for generation
and nomic-embed-text for embeddings. Both models can be changed in the `.env`
file without touching application code.

## Verify the installation

Open the health endpoint at `/api/health`. A status of `ok` means both the LLM
and the embedding provider are reachable. A status of `degraded` means one of
the providers is unavailable.