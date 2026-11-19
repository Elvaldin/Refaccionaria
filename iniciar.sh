#!/bin/bash
# Arranca la Refaccionaria completa:
#   5 microservicios en Python (8000-8004) + Gateway en Go (8080)
#
# Antes de arrancar revisa los puertos. Si uno está ocupado por una copia vieja
# de este mismo proyecto (por ejemplo, un microservicio que se quedó trabado),
# la cierra. Si lo ocupa otro programa, avisa cuál es y no arranca nada.
cd "$(dirname "$0")"

# El driver ODBC de SQL Server solo funciona con OpenSSL 1.1 o 3. Si Homebrew ya
# instaló OpenSSL 4 como "openssl", se le indica dónde está la versión 3.
if [ -d /opt/homebrew/opt/openssl@3/lib ]; then
    export DYLD_LIBRARY_PATH="/opt/homebrew/opt/openssl@3/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi
PROYECTO="$(pwd)"
source .venv/bin/activate

# nombre:puerto:carpeta de cada servicio
SERVICIOS="Login:8000:Backend/Login
Productos:8001:Backend/Productos
Promociones:8002:Backend/Promociones
Ordenes:8003:Backend/Ordenes
Soporte:8004:Backend/Soporte
Gateway:8080:Backend-Go/gateway"

# ---------- 1) La base de datos ----------
if ! nc -z 127.0.0.1 1433 2>/dev/null; then
    echo "⚠️  SQL Server no responde en el puerto 1433."
    echo "    ¿Está prendido Docker? Prueba:  docker start sql_server_container"
    echo "    (Se arranca de todos modos, pero las páginas no van a cargar datos.)"
    echo
fi

# ---------- 2) Los puertos ----------
# ¿Este proceso es de la Refaccionaria? (un uvicorn de este proyecto o el Gateway en Go)
es_del_proyecto() {
    local pid=$1
    local comando carpeta
    comando=$(ps -o command= -p "$pid" 2>/dev/null)
    carpeta=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
    case "$comando" in
        *"uvicorn API.main:app"*|*"go-build"*"/gateway"*|*"/gateway") ;;
        *) return 1 ;;
    esac
    case "$carpeta" in
        "$PROYECTO"/*) return 0 ;;
    esac
    # El Gateway compilado por "go run" corre desde la carpeta de caché de Go
    case "$comando" in *"go-build"*"/gateway"*) return 0 ;; esac
    return 1
}

# Cierra el proceso y sus hijos (uvicorn --reload tiene uno que vigila y otro que atiende)
cerrar() {
    local pid=$1
    local hijos
    hijos=$(pgrep -P "$pid")
    kill "$pid" $hijos 2>/dev/null
    for _ in 1 2 3 4 5 6; do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 0.5
    done
    kill -9 "$pid" $hijos 2>/dev/null   # se quedó trabado: se cierra a la fuerza
}

hay_problema=0
while IFS=: read -r nombre puerto carpeta; do
    for pid in $(lsof -ti tcp:"$puerto" -sTCP:LISTEN 2>/dev/null); do
        # uvicorn --reload tiene 2 procesos en el mismo puerto: al cerrar el primero,
        # el segundo (su hijo) ya se cerró con él y aquí se brinca
        kill -0 "$pid" 2>/dev/null || continue
        if es_del_proyecto "$pid"; then
            echo "🔄 $nombre: había una copia vieja en el puerto $puerto (proceso $pid). Se cierra."
            cerrar "$pid"
        else
            echo "❌ $nombre: el puerto $puerto lo está usando otro programa:"
            # Sin la ruta larga del programa: "Python -m http.server 8000" en vez de "/Library/.../Python ..."
            echo "     proceso $pid: $(ps -o command= -p "$pid" | sed 's#^[^ ]*/##' | cut -c1-90)"
            hay_problema=1
        fi
    done
done <<< "$SERVICIOS"

if [ $hay_problema -eq 1 ]; then
    echo
    echo "Cierra ese programa (o cambia el puerto) y vuelve a correr ./iniciar.sh"
    exit 1
fi

# Se espera a que los puertos queden libres de verdad
for _ in $(seq 1 10); do
    ocupado=0
    while IFS=: read -r nombre puerto carpeta; do
        lsof -ti tcp:"$puerto" -sTCP:LISTEN >/dev/null 2>&1 && ocupado=1
    done <<< "$SERVICIOS"
    [ $ocupado -eq 0 ] && break
    sleep 0.5
done

# ---------- 3) Arrancar ----------
# Al presionar Ctrl+C se apagan todos juntos
trap "kill 0" EXIT

(cd Backend/Login       && uvicorn API.main:app --reload --port 8000) &
(cd Backend/Productos   && uvicorn API.main:app --reload --port 8001) &
(cd Backend/Promociones && uvicorn API.main:app --reload --port 8002) &
(cd Backend/Ordenes     && uvicorn API.main:app --reload --port 8003) &
(cd Backend/Soporte     && uvicorn API.main:app --reload --port 8004) &
(cd Backend-Go/gateway  && go run .) &

# ---------- 4) Revisar que cada uno conteste ----------
# (El Gateway tarda más la primera vez porque Go lo compila)
echo
echo "Esperando a que arranquen…"
todos_bien=1
while IFS=: read -r nombre puerto carpeta; do
    ruta="/openapi.json"
    [ "$nombre" = "Gateway" ] && ruta="/"
    listo=0
    for _ in $(seq 1 60); do
        if curl -s -m 2 -o /dev/null "http://127.0.0.1:$puerto$ruta"; then listo=1; break; fi
        sleep 0.5
    done
    if [ $listo -eq 1 ]; then
        if [ "$nombre" = "Gateway" ]; then
            printf "✅ %-12s http://127.0.0.1:%s/   <- la página web usa este\n" "$nombre" "$puerto"
        else
            printf "✅ %-12s http://127.0.0.1:%s/docs\n" "$nombre" "$puerto"
        fi
    else
        printf "❌ %-12s no contesta en el puerto %s (revisa el error arriba)\n" "$nombre" "$puerto"
        todos_bien=0
    fi
done <<< "$SERVICIOS"

echo
if [ $todos_bien -eq 1 ]; then
    echo "Todo listo. Abre http://127.0.0.1:8080/ en el navegador. Para apagar todo: Ctrl+C"
else
    echo "Algún servicio no arrancó. Para apagar todo: Ctrl+C"
fi

wait
