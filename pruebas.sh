#!/bin/bash
# Corre todas las pruebas automáticas de la Refaccionaria.
#   1) Casos de uso de los 5 microservicios (no necesitan base de datos)
#   2) APIs de punta a punta por el Gateway (necesita ./iniciar.sh corriendo)
cd "$(dirname "$0")"

# El driver ODBC de SQL Server solo funciona con OpenSSL 1.1 o 3. Si Homebrew ya
# instaló OpenSSL 4 como "openssl", se le indica dónde está la versión 3.
if [ -d /opt/homebrew/opt/openssl@3/lib ]; then
    export DYLD_LIBRARY_PATH="/opt/homebrew/opt/openssl@3/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
fi
PY=.venv/bin/python
fallas=0

echo "===== 1) Casos de uso (sin base de datos) ====="
for s in Login Productos Promociones Ordenes Soporte; do
    printf "%-12s " "$s:"
    if salida=$(cd Backend/$s && ../../$PY -m unittest discover -s tests -t . 2>&1); then
        echo "$salida" | grep -E "^Ran" | tr -d '\n'; echo "  ✅"
    else
        echo "❌"; echo "$salida"; fallas=1
    fi
done

echo
echo "===== 2) APIs por el Gateway ====="
salida=$($PY pruebas/prueba_api.py -v 2>&1) || fallas=1
echo "$salida" | grep -E "\.\.\. |^Ran|^OK|^FAILED|skipped|Error|assert" | tail -n 30

echo
if [ $fallas -eq 0 ]; then echo "✅ Todas las pruebas pasaron"; else echo "❌ Hay pruebas que fallaron"; fi
exit $fallas
