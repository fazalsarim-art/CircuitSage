# CircuitSage frontend — production image.
# Stage 1 builds the static bundle with Vite; stage 2 serves it with nginx and reverse-proxies
# /api to the backend service so the SPA can use a relative API base URL.

FROM node:22.12.0-bookworm-slim AS builder

WORKDIR /app

# Install exactly the locked dependency tree.
COPY package.json package-lock.json ./
RUN npm ci

# The SPA talks to the API via a relative path; nginx proxies it to the backend in compose.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY . .
RUN npm run build


FROM nginx:1.27.3-bookworm AS runtime

# SPA history fallback + reverse proxy for the API. Written inline to keep the container config
# self-contained (no extra tracked config file).
RUN printf '%s\n' \
    'server {' \
    '  listen 8080;' \
    '  server_name _;' \
    '  root /usr/share/nginx/html;' \
    '  index index.html;' \
    '  location /api/ {' \
    '    proxy_pass http://api:8000;' \
    '    proxy_set_header Host $host;' \
    '    proxy_set_header X-Real-IP $remote_addr;' \
    '    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
    '    proxy_set_header X-Forwarded-Proto $scheme;' \
    '  }' \
    '  location / {' \
    '    try_files $uri $uri/ /index.html;' \
    '  }' \
    '}' \
    > /etc/nginx/conf.d/default.conf \
    && rm -f /etc/nginx/conf.d/default.conf.default 2>/dev/null || true

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
