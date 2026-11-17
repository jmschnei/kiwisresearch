# Dashboard: built once, served by nginx, which also proxies /api, /ws and /health to the API container.
# Build context must be ./ui
FROM node:22-alpine AS build
WORKDIR /ui
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Relative URLs: the browser talks to nginx on its own origin (no CORS, no hard-coded host)
ENV VITE_API_BASE_URL=/api/v1 VITE_WS_URL=/ws/events
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 80
