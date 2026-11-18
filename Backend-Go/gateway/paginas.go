package main

import (
	"io"
	"net/http"
	"strings"
	"time"
)

// "/" : lista de todas las APIs con su dirección completa
// y si cada microservicio de Python está encendido
func inicio(w http.ResponseWriter, r *http.Request) {
	gateway := "http://" + r.Host
	cliente := http.Client{Timeout: time.Second}

	html := `<h1>Refaccionaria - Gateway en Go</h1>
<p>Todas las APIs de los microservicios de Python, en una sola dirección.
<a href="` + gateway + `/docs">Ver documentación</a></p>`

	for _, s := range servicios {
		estado := "✅ encendido"
		if respuesta, err := cliente.Get(s.URL + "/openapi.json"); err != nil {
			estado = "❌ apagado"
		} else {
			respuesta.Body.Close()
		}
		html += "<h2>" + s.Nombre + " <small>(" + s.URL + " " + estado + ")</small></h2><ul>"
		for _, ejemplo := range s.Ejemplos {
			html += `<li><a href="` + gateway + ejemplo + `">` + gateway + ejemplo + `</a></li>`
		}
		html += "</ul>"
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(html))
}

// "/docs" : una sola pantalla de Swagger con un menú para elegir el microservicio
func documentacion(w http.ResponseWriter, r *http.Request) {
	lista := []string{}
	for _, s := range servicios {
		lista = append(lista, `{ url: "/openapi/`+s.Clave+`.json", name: "`+s.Nombre+`" }`)
	}
	pagina := strings.Replace(paginaDocs, "LISTA", strings.Join(lista, ", "), 1)
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write([]byte(pagina))
}

// "/openapi/{clave}.json" : trae la documentación que FastAPI ya genera en cada Python
func especificacion(w http.ResponseWriter, r *http.Request) {
	clave := strings.TrimSuffix(r.PathValue("archivo"), ".json")
	for _, s := range servicios {
		if s.Clave != clave {
			continue
		}
		cliente := http.Client{Timeout: 3 * time.Second}
		respuesta, err := cliente.Get(s.URL + "/openapi.json")
		if err != nil {
			responderJSON(w, http.StatusBadGateway, map[string]string{"detail": s.Nombre + " no responde"})
			return
		}
		defer respuesta.Body.Close()
		w.Header().Set("Content-Type", "application/json")
		io.Copy(w, respuesta.Body)
		return
	}
	http.NotFound(w, r)
}

const paginaDocs = `<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Gateway Refaccionaria - Swagger UI</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-standalone-preset.js"></script>
    <script>
        SwaggerUIBundle({
            urls: [ LISTA ],
            dom_id: "#swagger-ui",
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
            layout: "StandaloneLayout"
        });
    </script>
</body>
</html>`
