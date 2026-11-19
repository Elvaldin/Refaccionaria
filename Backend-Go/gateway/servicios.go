package main

import (
	"os"
	"strings"
)

// Servicio es un microservicio de Python al que el Gateway le reenvía peticiones
type Servicio struct {
	Nombre   string   // para mostrarlo en la página de inicio y en /docs
	Clave    string   // nombre corto, se usa en /openapi/{clave}.json
	URL      string   // dónde está corriendo el microservicio de Python
	Rutas    []string // las rutas que le tocan a ese microservicio
	Ejemplos []string // direcciones que se muestran en la página de inicio
}

// La tabla del Gateway: qué ruta va a qué microservicio de Python.
// Las URL de aquí son las de tu computadora (iniciar.sh). En Docker o en
// Google Cloud cada una se cambia con una variable de entorno: URL_LOGIN,
// URL_PRODUCTOS, URL_PROMOCIONES, URL_ORDENES y URL_SOPORTE.
var servicios = []Servicio{
	{
		Nombre: "Login", Clave: "login", URL: "http://127.0.0.1:8000",
		Rutas:    []string{"/api/login", "/api/usuarios"},
		Ejemplos: []string{"/api/login", "/api/usuarios"},
	},
	{
		Nombre: "Productos", Clave: "productos", URL: "http://127.0.0.1:8001",
		Rutas:    []string{"/api/categorias", "/api/productos"},
		Ejemplos: []string{"/api/categorias", "/api/productos", "/api/productos/1"},
	},
	{
		Nombre: "Promociones", Clave: "promociones", URL: "http://127.0.0.1:8002",
		Rutas:    []string{"/api/dashboard", "/api/promociones"},
		Ejemplos: []string{"/api/dashboard", "/api/promociones"},
	},
	{
		Nombre: "Ordenes", Clave: "ordenes", URL: "http://127.0.0.1:8003",
		Rutas:    []string{"/api/ordenes", "/api/inventario"},
		Ejemplos: []string{"/api/ordenes", "/api/inventario/movimientos"},
	},
	{
		Nombre: "Soporte", Clave: "soporte", URL: "http://127.0.0.1:8004",
		Rutas:    []string{"/api/soporte", "/api/conversaciones"},
		Ejemplos: []string{"/api/soporte", "/api/conversaciones?id_login=1"},
	},
}

// usarURLsDelEntorno cambia la URL de cada microservicio si viene en una
// variable de entorno (por ejemplo URL_LOGIN=http://login:8080 en Docker)
func usarURLsDelEntorno() {
	for i := range servicios {
		if url := os.Getenv("URL_" + strings.ToUpper(servicios[i].Clave)); url != "" {
			servicios[i].URL = url
		}
	}
}
