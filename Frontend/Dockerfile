# ── Stage 1: Build ───────────────────────────────────────────────────────────
# Install deps and run Vite build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .
RUN npm run build
# Output is in /app/dist

# ── Stage 2: Serve ────────────────────────────────────────────────────────────
# Copy the compiled dist/ into nginx and serve it
FROM nginx:alpine

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Defaults for same-machine compose; override at runtime for multi-PC deploys.
ENV DASHBOARD_HOST=dashboard
ENV DASHBOARD_PORT=8000

# The official nginx entrypoint renders templates from /etc/nginx/templates.
COPY default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
