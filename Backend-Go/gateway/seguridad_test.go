package main

// Pruebas de los encabezados de seguridad, CORS y el límite de registros:
//   cd Backend-Go/gateway && go test ./...

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

var ok = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK) })

func TestEncabezadosDeSeguridad(t *testing.T) {
	w := httptest.NewRecorder()
	conCabeceras(ok).ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/api/productos", nil))
	for nombre, valor := range map[string]string{
		"X-Content-Type-Options": "nosniff",
		"X-Frame-Options":        "DENY",
		"Referrer-Policy":        "same-origin",
	} {
		if got := w.Header().Get(nombre); got != valor {
			t.Errorf("%s = %q, se esperaba %q", nombre, got, valor)
		}
	}
	// Por HTTP (tu computadora) no se pide HTTPS
	if w.Header().Get("Strict-Transport-Security") != "" {
		t.Error("no debe mandar HSTS por HTTP")
	}
}

func TestHSTSSoloDetrasDeGoogleConHTTPS(t *testing.T) {
	r := httptest.NewRequest(http.MethodGet, "/", nil)
	r.Header.Set("X-Forwarded-Proto", "https")

	conProxies(t, 0) // sin proxy, ese encabezado lo pudo escribir cualquiera
	w := httptest.NewRecorder()
	conCabeceras(ok).ServeHTTP(w, r)
	if w.Header().Get("Strict-Transport-Security") != "" {
		t.Error("sin proxy no se le cree a X-Forwarded-Proto")
	}

	conProxies(t, 1)
	w = httptest.NewRecorder()
	conCabeceras(ok).ServeHTTP(w, r)
	if !strings.HasPrefix(w.Header().Get("Strict-Transport-Security"), "max-age=") {
		t.Error("detrás de Google con https debe mandar HSTS")
	}
}

func TestLaPaginaLlevaCSP(t *testing.T) {
	carpeta := t.TempDir()
	os.WriteFile(filepath.Join(carpeta, "index.html"), []byte("<h1>hola</h1>"), 0o644)
	w := httptest.NewRecorder()
	paginaWeb(carpeta).ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/", nil))
	csp := w.Header().Get("Content-Security-Policy")
	if w.Code != http.StatusOK || !strings.Contains(csp, "script-src 'self'") || strings.Contains(csp, "unsafe-inline") {
		t.Fatalf("código %d, CSP %q", w.Code, csp)
	}
}

func TestLeerCORS(t *testing.T) {
	casos := []struct {
		valor      string
		produccion bool
		todos      bool
		permitido  string
		error      bool
	}{
		{"", false, true, "", false}, // tu computadora: cualquiera (index.html con doble clic)
		{"", true, false, "", false}, // producción: nadie más
		{"*", true, true, "", false}, // se puede abrir a propósito
		{"https://mitienda.com/, https://otra.mx", true, false, "https://mitienda.com", false},
		{"mitienda.com", true, false, "", true}, // le falta https://
	}
	for _, c := range casos {
		t.Setenv("CORS_ORIGENES", c.valor)
		cfg, err := leerCORS(c.produccion)
		if (err != nil) != c.error {
			t.Errorf("%q: err = %v", c.valor, err)
			continue
		}
		if c.error {
			continue
		}
		if cfg.todos != c.todos || (c.permitido != "" && !cfg.origenes[c.permitido]) {
			t.Errorf("%q produccion=%v: %+v", c.valor, c.produccion, cfg)
		}
	}
}

func TestCORSSoloParaLosSitiosPermitidos(t *testing.T) {
	cfg := configCORS{origenes: map[string]bool{"https://mitienda.com": true}}
	pedir := func(origen string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(http.MethodGet, "/api/productos", nil)
		r.Header.Set("Origin", origen)
		w := httptest.NewRecorder()
		conCORS(cfg, ok).ServeHTTP(w, r)
		return w
	}
	if got := pedir("https://mitienda.com").Header().Get("Access-Control-Allow-Origin"); got != "https://mitienda.com" {
		t.Errorf("sitio permitido: %q", got)
	}
	if got := pedir("https://malo.example").Header().Get("Access-Control-Allow-Origin"); got != "" {
		t.Errorf("sitio no permitido recibió %q", got)
	}
}

func TestPreflightContestaSinLlegarAPython(t *testing.T) {
	r := httptest.NewRequest(http.MethodOptions, "/api/ordenes", nil)
	r.Header.Set("Origin", "https://malo.example")
	r.Header.Set("Access-Control-Request-Method", "POST")
	w := httptest.NewRecorder()
	llego := false
	conCORS(configCORS{}, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { llego = true })).ServeHTTP(w, r)
	if llego || w.Code != http.StatusNoContent || w.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Fatalf("llegó=%v código=%d ACAO=%q", llego, w.Code, w.Header().Get("Access-Control-Allow-Origin"))
	}
}

func TestLimiteDeRegistrosPorIP(t *testing.T) {
	conProxies(t, 0)
	limite := limitarRegistro(ok)
	registrar := func(ip string) int {
		r := httptest.NewRequest(http.MethodPost, "/api/usuarios", strings.NewReader(`{}`))
		r.RemoteAddr = ip + ":5000"
		w := httptest.NewRecorder()
		limite.ServeHTTP(w, r)
		return w.Code
	}
	for i := 0; i < maxRegistrosPorIP; i++ {
		if codigo := registrar("198.51.100.66"); codigo != http.StatusOK {
			t.Fatalf("intento %d: %d", i+1, codigo)
		}
	}
	if codigo := registrar("198.51.100.66"); codigo != http.StatusTooManyRequests {
		t.Fatalf("el intento %d debía ser 429, fue %d", maxRegistrosPorIP+1, codigo)
	}
	if codigo := registrar("203.0.113.7"); codigo != http.StatusOK {
		t.Fatalf("otra IP debía poder registrarse, recibió %d", codigo)
	}
	// Las demás rutas no cuentan
	r := httptest.NewRequest(http.MethodGet, "/api/productos", nil)
	r.RemoteAddr = "198.51.100.66:5000"
	w := httptest.NewRecorder()
	limite.ServeHTTP(w, r)
	if w.Code != http.StatusOK {
		t.Fatalf("GET /api/productos: %d", w.Code)
	}
}
