package main

import (
	"encoding/json"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
)

// nuevoProxy crea el "reenviador" hacia un microservicio de Python.
// httputil.ReverseProxy ya viene en Go: recibe la petición, se la pasa
// a Python tal cual y le regresa al navegador lo que Python conteste.
func nuevoProxy(servicio Servicio) http.Handler {
	destino, err := url.Parse(servicio.URL)
	if err != nil {
		log.Fatalf("La URL de %s no es válida: %v", servicio.Nombre, err)
	}
	proxy := httputil.NewSingleHostReverseProxy(destino)

	// Si el microservicio de Python está apagado, se avisa con un error claro
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Printf("ERROR: %s no responde: %v", servicio.Nombre, err)
		responderJSON(w, http.StatusBadGateway, map[string]string{
			"detail": "El microservicio de " + servicio.Nombre + " (" + servicio.URL + ") no responde. ¿Está corriendo?",
		})
	}
	return proxy
}

func responderJSON(w http.ResponseWriter, estado int, datos any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(estado)
	json.NewEncoder(w).Encode(datos)
}

// conCORS deja que la página web (otro puerto) pueda llamar al Gateway
func conCORS(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		siguiente.ServeHTTP(w, r)
	})
}

// conRegistro escribe en la terminal cada petición
func conRegistro(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		log.Printf("%s %s", r.Method, r.URL.RequestURI())
		siguiente.ServeHTTP(w, r)
	})
}
