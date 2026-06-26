# =============================================================================
# Frontend Dockerfile
# =============================================================================
# WHY standalone output:
#   Next.js standalone mode bundles only the files needed to run the
#   server — no node_modules in the final image. The runtime image drops
#   from ~400MB to ~100MB.
#   Requires `output: 'standalone'` in next.config.ts (see that file).
# =============================================================================

# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first for layer caching
COPY package*.json ./
RUN npm ci --frozen-lockfile

# Copy source and build
COPY . .

# NEXT_PUBLIC_API_URL is baked into the JS bundle at build time.
# Inside the Docker network, frontend talks to backend service by name.
# For browser requests (client-side fetches), this needs to be the
# publicly accessible URL — override at deploy time if needed.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ── Stage 2: Runtime (standalone output) ──────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Next.js standalone output structure:
#   .next/standalone/  — server + minimal node_modules
#   .next/static/      — client-side JS/CSS chunks
#   public/            — static assets
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

# Standalone mode uses server.js directly — not `npm run start`
CMD ["node", "server.js"]
