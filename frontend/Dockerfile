# ============================================================================
# Dockerfile — TicketU Front-end
# ----------------------------------------------------------------------------
# Build multi-stage.
#
# NEXT_PUBLIC_GATEWAY_URL se pasa durante el build porque Next.js incorpora
# las variables NEXT_PUBLIC_* al bundle que ejecutará el navegador.
# ============================================================================

FROM node:20-alpine AS builder
WORKDIR /app

ARG NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080
ENV NEXT_PUBLIC_GATEWAY_URL=${NEXT_PUBLIC_GATEWAY_URL}

# Módulo Pagos: llave publicable de Stripe (pk_test_...) y página de login opcional.
ARG NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
ENV NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=${NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY}
ARG NEXT_PUBLIC_LOGIN_URL=
ENV NEXT_PUBLIC_LOGIN_URL=${NEXT_PUBLIC_LOGIN_URL}

COPY package*.json ./
RUN npm ci

COPY . .

# El repositorio puede no tener una carpeta public todavía.
RUN mkdir -p public

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/package-lock.json ./package-lock.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./next.config.js

EXPOSE 3000

CMD ["npm", "run", "start"]
