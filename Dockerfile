FROM node:22-bookworm-slim AS frontend
WORKDIR /build
RUN corepack enable && corepack prepare pnpm@10.17.1 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --ignore-workspace
COPY frontend/ ./
ENV SITESYNC_STANDALONE=true NEXT_TELEMETRY_DISABLED=1
RUN pnpm exec next build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /build/.next/standalone /app/frontend
COPY --from=frontend /build/.next/static /app/frontend/.next/static
COPY deploy/serve.py /app/serve.py
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["python", "/app/serve.py"]
