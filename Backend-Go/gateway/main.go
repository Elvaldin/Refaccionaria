package main

import (
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

func main() {
	usarURLsDelEntorno()
	var err error
	if proxiesDeConfianza, err = leerProxiesDeConfianza(); err != nil {
		log.Fatal(err)
	}
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

	// La página web (Frontend) se entrega desde aquí mismo, en "/".
	// Las rutas /api/... de arriba tienen prioridad porque son más específicas.
	carpeta := carpetaFrontend()
	if _, err := os.Stat(filepath.Join(carpeta, "index.html")); err != nil {
		log.Fatalf("No encuentro la página web en %s (usa FRONTEND=<carpeta del Frontend>): %v", carpeta, err)
	}
	rutas.Handle("/", paginaWeb(carpeta))
	rutas.HandleFunc("/api/", apiNoExiste)

	// Las páginas de ayuda ("/gateway" y "/docs") muestran direcciones y puertos internos:
	// sirven para desarrollar y para la demo, pero en producción no se publican.
	// Para apagarlas: ENTORNO=produccion
	produccion := os.Getenv("ENTORNO") == "produccion"
	cors, err := leerCORS(produccion)
	if err != nil {
		log.Fatal(err)
	}
	if !produccion {
		rutas.HandleFunc("GET /gateway", inicio)
		rutas.HandleFunc("GET /docs", documentacion)
		rutas.HandleFunc("GET /openapi/{archivo}", especificacion)
	}

	// Puerto: PUERTO (iniciar.sh), o PORT, que es el que pone Google Cloud Run
	puerto := os.Getenv("PUERTO")
	if puerto == "" {
		puerto = os.Getenv("PORT")
	}
	if puerto == "" {
		puerto = "8080"
	}
	// En tu computadora solo escucha en 127.0.0.1 (nadie de fuera entra).
	// Dentro de un contenedor tiene que ser HOST=0.0.0.0 para que llegue el tráfico.
	host := os.Getenv("HOST")
	if host == "" {
		host = "127.0.0.1"
	}
	direccion := host + ":" + puerto

	// Tiempos máximos: así una conexión lenta (o alguien que la deja abierta
	// a propósito) no se queda ocupando el Gateway para siempre
	servidor := &http.Server{
		Addr:              direccion,
		Handler:           conCabeceras(conCORS(cors, conRegistro(limitarTamano(limitarLogin(limitarRegistro(rutas)))))),
		ReadHeaderTimeout: 5 * time.Second,  // para mandar los encabezados
		ReadTimeout:       15 * time.Second, // para mandar toda la petición
		WriteTimeout:      30 * time.Second, // para contestar
		IdleTimeout:       60 * time.Second, // conexión abierta sin hacer nada
		MaxHeaderBytes:    64 << 10,         // 64 KB de encabezados
	}

	if produccion {
		log.Printf("Gateway (Go) corriendo en http://%s/ (modo producción: sin /gateway ni /docs)", direccion)
	} else {
		log.Printf("Gateway (Go) corriendo en http://%s/", direccion)
	}
	if proxiesDeConfianza > 0 {
		log.Printf("Límite de login: IP del visitante = la %d.ª de X-Forwarded-For contando desde la derecha", proxiesDeConfianza)
	} else {
		log.Printf("Límite de login: IP de la conexión (sin proxy delante)")
	}
	log.Printf("CORS: la API acepta llamadas del navegador desde %s", cors)
	log.Fatal(servidor.ListenAndServe())
}
