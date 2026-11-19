# Gateway en Go + la página web (Frontend) dentro de un contenedor.
# Se construye desde la carpeta principal del proyecto, porque necesita
# Backend-Go/gateway (el programa) y Frontend (la página):
#   docker build -f Backend-Go/gateway/Dockerfile -t refaccionaria-gateway .
#
# Se hace en 2 partes: la primera imagen (con Go completo) solo compila;
# la final lleva únicamente el programa ya compilado y la página (unos 19 MB).

# ---- 1) Compilar ----
FROM golang:1.27-bookworm AS compilar
WORKDIR /src
COPY Backend-Go/gateway/go.mod ./
COPY Backend-Go/gateway/*.go ./
# CGO_ENABLED=0: un solo archivo que no depende de nada más del sistema
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /gateway .

# ---- 2) Imagen final ----
# distroless: sin shell ni programas extra, y corre sin permisos de administrador (nonroot)
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=compilar /gateway /gateway
COPY Frontend/ /frontend/

# Dentro del contenedor tiene que escuchar en todas las interfaces.
# FRONTEND: dónde quedó la página. Las URL de los microservicios se dan
# con URL_LOGIN, URL_PRODUCTOS, etc.
ENV HOST=0.0.0.0 \
    FRONTEND=/frontend
EXPOSE 8080
ENTRYPOINT ["/gateway"]
