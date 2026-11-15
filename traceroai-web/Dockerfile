# TraceroAI web (landing, docs, dashboard).
#
# Two API URLs, because the page renders in two places:
#   NEXT_PUBLIC_TRACEROAI_API_URL  build arg; baked into browser code, so it must
#                                  be reachable from the user's browser.
#   TRACEROAI_API_URL              runtime env; used by server rendering, so it can
#                                  be an internal address such as http://api:8000.
FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG NEXT_PUBLIC_TRACEROAI_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_TRACEROAI_API_URL=$NEXT_PUBLIC_TRACEROAI_API_URL
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

# node_modules is copied whole (dev dependencies included) so next.config.ts
# loads exactly as it did at build time.
COPY --from=build --chown=node:node /app/package.json /app/next.config.ts ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next ./.next

USER node
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
