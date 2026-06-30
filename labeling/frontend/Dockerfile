# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY labeling/frontend/package.json labeling/frontend/package-lock.json* ./
RUN npm install
COPY labeling/frontend/ .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY labeling/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
