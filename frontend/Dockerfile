# ---- Frontend (build with Node, serve with nginx) ----
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

# brief §38: container-level health check. Non-root hardening for the
# nginx stage is NOT done here — nginx:alpine binding to port 80 as a
# non-root user needs either a capability grant (cap_net_bind_service) or
# switching to port >1024 + a reverse proxy in front, and getting that
# wrong produces a container that silently fails to serve anything. That
# trade-off needs a real `docker build && docker run` cycle to verify,
# which this development environment can't do — see REMAINING_WORK.md.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
