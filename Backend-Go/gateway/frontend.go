package main

import (
	"net/http"
	"os"
	"strings"
)

// carpetaFrontend dice dónde están index.html, estilo.css, script.js e img/.
// En tu computadora (go run . desde Backend-Go/gateway) es ../../Frontend.
// En Docker y en Google Cloud se da con la variable FRONTEND=/frontend
func carpetaFrontend() string {
	if carpeta := os.Getenv("FRONTEND"); carpeta != "" {
		return carpeta
	}
	return "../../Frontend"
}

// paginaWeb entrega los archivos de la página (HTML, CSS, JS e imágenes)
// desde la misma dirección que las APIs. Así la página le pide los datos
// a "/api" y funciona en cualquier dominio donde se publique.
func paginaWeb(carpeta string) http.Handler {
	archivos := http.FileServer(http.Dir(carpeta))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			http.Error(w, "Método no permitido", http.StatusMethodNotAllowed)
			return
		}
		// No se enseña la lista de archivos de una carpeta (img/productos/)
		// ni archivos ocultos como .DS_Store
		if (r.URL.Path != "/" && strings.HasSuffix(r.URL.Path, "/")) || strings.Contains(r.URL.Path, "/.") {
			http.NotFound(w, r)
			return
		}
		archivos.ServeHTTP(w, r)
	})
}

// apiNoExiste contesta en JSON cuando piden una ruta /api/... que no es de
// ningún microservicio (sin esto, la contestaría la página web con un 404 en texto)
func apiNoExiste(w http.ResponseWriter, r *http.Request) {
	responderJSON(w, http.StatusNotFound, map[string]string{"detail": "Esa ruta de la API no existe."})
}
