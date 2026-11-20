# =============================================================================
# Build Stage
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# =============================================================================
# Production Stage (Non-Root Unprivileged Nginx)
# =============================================================================
# Uses official unprivileged image running as user 101 (nginx) on port 8080
FROM nginx/nginx-unprivileged:1.30.7-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

USER 101

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
