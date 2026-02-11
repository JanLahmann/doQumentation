# Stage 1: Build the Docusaurus site
FROM node:20-alpine AS build

RUN apk add --no-cache python3 git

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN python3 scripts/sync-content.py
RUN NODE_OPTIONS="--max-old-space-size=8192" npm run build

# Remove GitHub Pages CNAME from build output
RUN rm -f build/CNAME

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO /dev/null http://localhost:80/ || exit 1
