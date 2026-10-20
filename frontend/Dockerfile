FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Static file server only; TLS and /api,/ws routing live in the edge `caddy` service.
FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile.static /etc/caddy/Caddyfile
