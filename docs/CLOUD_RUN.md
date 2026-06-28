# Cloud Run deployment

Kairos ships a slim Docker image (`Dockerfile`) that uses **Gemini API embeddings** — no `sentence-transformers` in the container.

## Build and deploy

```bash
gcloud run deploy kairos \
  --source . \
  --region us-central1 \
  --min-instances 1 \
  --memory 512Mi \
  --set-env-vars "EMBEDDING_BACKEND=gemini,MONGODB_VECTOR_SEARCH_ENABLED=true" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest,MONGODB_URI=mongodb-uri:latest"
```

Required env vars:

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | LLM + embeddings |
| `MONGODB_URI` | Atlas connection string |
| `KAIROS_USER_ID` | Active user after Google OAuth |
| `EMBEDDING_BACKEND` | `gemini` (default in container) |

## Atlas vector search

On first `kairos bookmarks cluster`, Kairos attempts to create vector search indexes:

- `clusters_centroid` on `clusters.centroid_embedding`
- `bookmarks_embedding` on `bookmarks.embedding`

Dimensions must match `GEMINI_EMBEDDING_DIMENSIONS` (default 768). If indexes cannot be created (local MongoDB), ranking falls back to in-memory cosine similarity.

Disable vector search: `MONGODB_VECTOR_SEARCH_ENABLED=false`

## Local dev with offline embeddings

```bash
uv sync --extra local
EMBEDDING_BACKEND=local kairos bookmarks embed && kairos bookmarks cluster
```

Re-embed after switching between `gemini` and `local` — vector spaces are incompatible.
