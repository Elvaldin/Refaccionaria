package main

import (
	"log"
	"net/http"
	"os"
	"time"
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

	// Las páginas de ayuda ("/" y "/docs") muestran direcciones y puertos internos:
	// sirven para desarrollar y para la demo, pero en producción no se publican.
	// Para apagarlas: ENTORNO=produccion
	produccion := os.Getenv("ENTORNO") == "produccion"
	if !produccion {
		rutas.HandleFunc("GET /{$}", inicio)
		rutas.HandleFunc("GET /docs", documentacion)
		rutas.HandleFunc("GET /openapi/{archivo}", especificacion)
	}

	puerto := os.Getenv("PUERTO")
	if puerto == "" {
		puerto = "8080"
	}
	direccion := "127.0.0.1:" + puerto

	// Tiempos máximos: así una conexión lenta (o alguien que la deja abierta
	// a propósito) no se queda ocupando el Gateway para siempre
	servidor := &http.Server{
		Addr:              direccion,
		Handler:           conCORS(conRegistro(limitarTamano(limitarLogin(rutas)))),
		ReadHeaderTimeout: 5 * time.Second,  // para mandar los encabezados
		ReadTimeout:       15 * time.Second, // para mandar toda la petición
		WriteTimeout:      30 * time.Second, // para contestar
		IdleTimeout:       60 * time.Second, // conexión abierta sin hacer nada
		MaxHeaderBytes:    64 << 10,         // 64 KB de encabezados
	}

	if produccion {
		log.Printf("Gateway (Go) corriendo en http://%s/ (modo producción: sin / ni /docs)", direccion)
	} else {
		log.Printf("Gateway (Go) corriendo en http://%s/", direccion)
	}
	log.Fatal(servidor.ListenAndServe())
}
