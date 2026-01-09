# syntax=docker/dockerfile:1

# Build the Vite app
FROM node:22-alpine AS build
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build with the provided API base URL
COPY . .
# VITE_BUILD_MODE controls which Vite env files are used (.env, .env.production, etc.)
ARG VITE_BUILD_MODE=production
RUN npm run build -- --mode ${VITE_BUILD_MODE}

# Serve the static files with nginx
FROM nginx:1.27-alpine AS runner
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
