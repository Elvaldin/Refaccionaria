# Gateway en Go dentro de un contenedor.
#   docker build -t refaccionaria-gateway Backend-Go/gateway
#
# Se hace en 2 partes: la primera imagen (con Go completo) solo compila;
# la final lleva únicamente el programa ya compilado (unos 10 MB).

# ---- 1) Compilar ----
FROM golang:1.27-bookworm AS compilar
WORKDIR /src
COPY go.mod ./
COPY *.go ./
# CGO_ENABLED=0: un solo archivo que no depende de nada más del sistema
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /gateway .

# ---- 2) Imagen final ----
# distroless: sin shell ni programas extra, y corre sin permisos de administrador (nonroot)
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=compilar /gateway /gateway

# Dentro del contenedor tiene que escuchar en todas las interfaces.
# Las URL de los microservicios se dan con URL_LOGIN, URL_PRODUCTOS, etc.
ENV HOST=0.0.0.0
EXPOSE 8080
ENTRYPOINT ["/gateway"]
