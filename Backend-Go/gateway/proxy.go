package main

import (
	"encoding/json"
	"errors"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"
)

// Tamaño máximo de una petición. La más grande de la página (una orden o una
// promoción con muchos productos) pesa unos pocos KB.
const tamanoMaximo = 1 << 20 // 1 MB

// nuevoProxy crea el "reenviador" hacia un microservicio de Python.
// httputil.ReverseProxy ya viene en Go: recibe la petición, se la pasa
// a Python tal cual y le regresa al navegador lo que Python conteste.
//
// identidad: con IDENTIDAD_GOOGLE=si, el token con el que el Gateway se
// identifica ante Google Cloud Run (nil = no hace falta, como en tu computadora).
func nuevoProxy(servicio Servicio, identidad *identidadGoogle) http.Handler {
	destino, err := url.Parse(servicio.URL)
	if err != nil {
		log.Fatalf("La URL de %s no es válida: %v", servicio.Nombre, err)
	}
	proxy := httputil.NewSingleHostReverseProxy(destino)
	dirigir := proxy.Director
	proxy.Director = func(r *http.Request) {
		dirigir(r)
		// Host = el del microservicio. En Cloud Run cada servicio tiene su propia
		// dirección (login-xxxx.run.app) y Google lo busca por este encabezado;
		// con el del Gateway contestaría 404
		r.Host = destino.Host
		// Nadie de fuera puede mandar su propio token de identidad
		r.Header.Del("X-Serverless-Authorization")
	}

	// Tiempos máximos para hablar con Python: si un microservicio se traba,
	// el Gateway no se queda esperando para siempre
	proxy.Transport = &http.Transport{
		DialContext:           (&net.Dialer{Timeout: 3 * time.Second}).DialContext,
		ResponseHeaderTimeout: 20 * time.Second,
		MaxIdleConnsPerHost:   20,
		IdleConnTimeout:       90 * time.Second,
	}
	if identidad != nil {
		proxy.Transport = transporteConIdentidad{base: proxy.Transport, identidad: identidad, audiencia: servicio.URL}
	}

	// Si algo sale mal, el detalle (dirección, puerto, error) se queda en la
	// terminal del Gateway; al navegador solo le llega un mensaje general
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		var muyGrande *http.MaxBytesError
		if errors.As(err, &muyGrande) {
			responderJSON(w, http.StatusRequestEntityTooLarge, map[string]string{
				"detail": "La petición es demasiado grande.",
			})
			return
		}
		log.Printf("ERROR: %s (%s) no responde: %v", servicio.Nombre, servicio.URL, err)
		responderJSON(w, http.StatusBadGateway, map[string]string{
			"detail": "El servicio de " + servicio.Nombre + " no está disponible. Intenta de nuevo en un momento.",
		})
	}
	// Lo que contesta Python: sin el encabezado "Server: uvicorn" (no hace falta
	// decir qué programa hay detrás) y sin guardarse en cachés, porque puede
	// llevar datos de la sesión (el token del login, las órdenes de alguien)
	proxy.ModifyResponse = func(respuesta *http.Response) error {
		respuesta.Header.Del("Server")
		if respuesta.Header.Get("Cache-Control") == "" {
			respuesta.Header.Set("Cache-Control", "no-store")
		}
		return nil
	}
	return proxy
}

func responderJSON(w http.ResponseWriter, estado int, datos any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(estado)
	json.NewEncoder(w).Encode(datos)
}

// limitarTamano rechaza peticiones de más de 1 MB (413), para que nadie
// pueda saturar a Python mandando cuerpos gigantes
func limitarTamano(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.ContentLength > tamanoMaximo {
			responderJSON(w, http.StatusRequestEntityTooLarge, map[string]string{
				"detail": "La petición es demasiado grande.",
			})
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, tamanoMaximo)
		siguiente.ServeHTTP(w, r)
	})
}

// conRegistro escribe en la terminal (o en Cloud Logging) cada petición, con la
// IP que usa el límite de login. Sirve para revisar que PROXIES_DE_CONFIANZA esté
// bien: al entrar a la tienda desde tu casa, debe salir la IP de tu casa
func conRegistro(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		log.Printf("%s %s %s", ipDe(r), r.Method, r.URL.RequestURI())
		siguiente.ServeHTTP(w, r)
	})
}
