FROM node:24-alpine AS build

WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:24-alpine AS runtime

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

RUN addgroup --system --gid 10001 mosaic \
    && adduser --system --uid 10001 mosaic

COPY --from=build --chown=mosaic:mosaic /app/public ./public
COPY --from=build --chown=mosaic:mosaic /app/.next/standalone ./
COPY --from=build --chown=mosaic:mosaic /app/.next/static ./.next/static

USER mosaic

EXPOSE 3000

CMD ["node", "server.js"]
