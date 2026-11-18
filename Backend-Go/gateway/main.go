package main

import (
	"log"
	"net/http"
	"os"
)

func main() {
	rutas := http.NewServeMux()

	// Cada ruta de la tabla se conecta con su microservicio de Python.
	// Se registra "/api/productos" y también "/api/productos/" para que
	// entren /api/productos/1, /api/productos/1/... etc.
	for _, servicio := range servicios {
		proxy := nuevoProxy(servicio)
		for _, ruta := range servicio.Rutas {
			rutas.Handle(ruta, proxy)
			rutas.Handle(ruta+"/", proxy)
		}
	}

	rutas.HandleFunc("GET /{$}", inicio)
	rutas.HandleFunc("GET /docs", documentacion)
	rutas.HandleFunc("GET /openapi/{archivo}", especificacion)

	puerto := os.Getenv("PUERTO")
	if puerto == "" {
		puerto = "8080"
	}
	direccion := "127.0.0.1:" + puerto

	log.Printf("Gateway (Go) corriendo en http://%s/", direccion)
	log.Fatal(http.ListenAndServe(direccion, conCORS((conRegistro(rutas)))))
}
