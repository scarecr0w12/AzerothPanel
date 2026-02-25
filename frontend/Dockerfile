# syntax=docker/dockerfile:1.4
# ─── Stage 1: build the React app ────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first (layer-cached unless package*.json changes)
COPY frontend/package*.json ./

# Use BuildKit cache mount to persist npm cache across builds
# This dramatically speeds up rebuilds as packages are cached
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy source and build
COPY frontend/ .

# Use cache mount for npm cache during build as well
RUN --mount=type=cache,target=/root/.npm \
    npm run build

# ─── Stage 2: serve with nginx ────────────────────────────────────────────────
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config (proxy to backend + SPA fallback)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

