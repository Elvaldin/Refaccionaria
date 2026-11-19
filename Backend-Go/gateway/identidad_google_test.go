package main

// Pruebas del proxy y del token de identidad de Google, con un servidor de
// metadatos y un microservicio de mentiras:
//   cd Backend-Go/gateway && go test ./...

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync/atomic"
	"testing"
)

// microservicio de mentiras: apunta lo que le llegó
type recibido struct {
	host, identidad, sesion string
}

func microservicioFalso(t *testing.T) (*httptest.Server, *recibido) {
	r := &recibido{}
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		r.host = req.Host
		r.identidad = req.Header.Get("X-Serverless-Authorization")
		r.sesion = req.Header.Get("Authorization")
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(s.Close)
	return s, r
}

func metadatosFalsos(t *testing.T, codigo int) *atomic.Int32 {
	var llamadas atomic.Int32
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		llamadas.Add(1)
		if req.Header.Get("Metadata-Flavor") != "Google" || req.URL.Query().Get("audience") == "" {
			http.Error(w, "falta Metadata-Flavor o audience", http.StatusBadRequest)
			return
		}
		w.WriteHeader(codigo)
		w.Write([]byte("token-de-" + req.URL.Query().Get("audience")))
	}))
	t.Cleanup(s.Close)
	anterior := urlMetadatos
	urlMetadatos = s.URL
	t.Cleanup(func() { urlMetadatos = anterior })
	return &llamadas
}

func pedirAlProxy(proxy http.Handler, cabeceras map[string]string) int {
	r := httptest.NewRequest(http.MethodGet, "http://gateway.example/api/productos", nil)
	for k, v := range cabeceras {
		r.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	proxy.ServeHTTP(w, r)
	return w.Code
}

func TestElProxyUsaElHostDelMicroservicio(t *testing.T) {
	ms, llego := microservicioFalso(t)
	proxy := nuevoProxy(Servicio{Nombre: "Productos", URL: ms.URL}, nil)
	pedirAlProxy(proxy, map[string]string{"X-Serverless-Authorization": "Bearer falso"})
	destino, _ := url.Parse(ms.URL)
	if llego.host != destino.Host {
		t.Errorf("Host = %q, se esperaba %q (el del microservicio, no el del Gateway)", llego.host, destino.Host)
	}
	if llego.identidad != "" {
		t.Errorf("un token de identidad que mandó el visitante no debe pasar: %q", llego.identidad)
	}
}

func TestConIdentidadGoogleMandaElTokenYConservaLaSesion(t *testing.T) {
	ms, llego := microservicioFalso(t)
	llamadas := metadatosFalsos(t, http.StatusOK)
	proxy := nuevoProxy(Servicio{Nombre: "Productos", URL: ms.URL}, nuevaIdentidadGoogle())

	codigo := pedirAlProxy(proxy, map[string]string{"Authorization": "Bearer sesion-del-usuario"})
	if codigo != http.StatusOK {
		t.Fatalf("código %d", codigo)
	}
	if llego.identidad != "Bearer token-de-"+ms.URL {
		t.Errorf("X-Serverless-Authorization = %q", llego.identidad)
	}
	if llego.sesion != "Bearer sesion-del-usuario" {
		t.Errorf("el token de sesión del usuario debe seguir en Authorization: %q", llego.sesion)
	}
	// La segunda vez usa el token guardado (no vuelve a pedirlo)
	pedirAlProxy(proxy, nil)
	if n := llamadas.Load(); n != 1 {
		t.Errorf("se pidió el token %d veces, se esperaba 1", n)
	}
}

func TestSinTokenDeGoogleContesta502(t *testing.T) {
	ms, _ := microservicioFalso(t)
	metadatosFalsos(t, http.StatusInternalServerError)
	proxy := nuevoProxy(Servicio{Nombre: "Productos", URL: ms.URL}, nuevaIdentidadGoogle())
	if codigo := pedirAlProxy(proxy, nil); codigo != http.StatusBadGateway {
		t.Fatalf("código %d, se esperaba 502", codigo)
	}
}
