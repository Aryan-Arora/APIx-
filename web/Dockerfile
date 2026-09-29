FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_API_KEY
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.ts ./
RUN useradd --create-home apix
USER apix
CMD ["sh", "-c", "npx next start -p ${PORT:-3000}"]
