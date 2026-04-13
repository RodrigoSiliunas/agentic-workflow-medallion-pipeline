# Stage 1: Install deps + build
FROM oven/bun:1-alpine AS builder

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

ENV NUXT_PUBLIC_MOCK_MODE=false
ENV NUXT_PUBLIC_API_BASE=/api/v1

RUN bun run build

# Stage 2: Production runtime
FROM node:22-alpine

WORKDIR /app

# Non-root user
RUN adduser --system --group app

# Copiar output do Nuxt build (SSR mode)
COPY --from=builder --chown=app:app /app/.output .output/

USER app

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -q --spider http://localhost:3000/ || exit 1

CMD ["node", ".output/server/index.mjs"]
