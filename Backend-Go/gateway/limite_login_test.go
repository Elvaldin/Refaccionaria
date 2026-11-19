package main

// Pruebas del límite de intentos de login. Se corren con:
//   cd Backend-Go/gateway && go test ./...

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func peticion(remoteAddr string, xff ...string) *http.Request {
	r := httptest.NewRequest(http.MethodPost, "/api/login", nil)
	r.RemoteAddr = remoteAddr
	for _, valor := range xff {
		r.Header.Add("X-Forwarded-For", valor)
	}
	return r
}

func conProxies(t *testing.T, n int) {
	anterior := proxiesDeConfianza
	proxiesDeConfianza = n
	t.Cleanup(func() { proxiesDeConfianza = anterior })
}

func TestSinProxySeUsaLaIPDeLaConexion(t *testing.T) {
	conProxies(t, 0)
	// Sin proxy, X-Forwarded-For lo escribe el visitante: no se le cree
	if ip := ipDe(peticion("203.0.113.7:51000", "1.2.3.4")); ip != "203.0.113.7" {
		t.Fatalf("ip = %q", ip)
	}
}

func TestDetrasDeCloudRunSeUsaLaUltimaDeXForwardedFor(t *testing.T) {
	conProxies(t, 1)
	if ip := ipDe(peticion("169.254.1.1:8080", "203.0.113.7")); ip != "203.0.113.7" {
		t.Fatalf("ip = %q", ip)
	}
}

func TestNoSePuedeFingirOtraIP(t *testing.T) {
	conProxies(t, 1)
	// El visitante manda "1.2.3.4" y Google agrega su IP real al final
	if ip := ipDe(peticion("169.254.1.1:8080", "1.2.3.4, 203.0.113.7")); ip != "203.0.113.7" {
		t.Fatalf("ip = %q", ip)
	}
	// Aunque mande el encabezado varias veces
	if ip := ipDe(peticion("169.254.1.1:8080", "1.2.3.4", "5.6.7.8, 203.0.113.7")); ip != "203.0.113.7" {
		t.Fatalf("ip = %q", ip)
	}
}

func TestConBalanceadorSeCuentanDosDesdeLaDerecha(t *testing.T) {
	conProxies(t, 2)
	// Balanceador de Google: "<lo que mandó el visitante>, <IP del visitante>, <IP del balanceador>"
	if ip := ipDe(peticion("169.254.1.1:8080", "1.2.3.4, 203.0.113.7, 34.111.0.1")); ip != "203.0.113.7" {
		t.Fatalf("ip = %q", ip)
	}
}

func TestSiFaltaElEncabezadoSeUsaLaConexion(t *testing.T) {
	conProxies(t, 1)
	if ip := ipDe(peticion("169.254.1.1:8080")); ip != "169.254.1.1" {
		t.Fatalf("ip = %q", ip)
	}
	if ip := ipDe(peticion("169.254.1.1:8080", "no-es-ip")); ip != "169.254.1.1" {
		t.Fatalf("ip = %q", ip)
	}
}

func TestIPv6SeAgrupaPorBloque(t *testing.T) {
	conProxies(t, 1)
	a := ipDe(peticion("169.254.1.1:8080", "2001:db8:1:2::10"))
	b := ipDe(peticion("169.254.1.1:8080", "2001:db8:1:2:ffff::99"))
	if a != b || !strings.HasSuffix(a, "/64") {
		t.Fatalf("a = %q, b = %q", a, b)
	}
}

func TestPROXIES_DE_CONFIANZA(t *testing.T) {
	casos := map[string]bool{"": true, "0": true, "1": true, "2": true, "-1": false, "uno": false, "9": false}
	for valor, valido := range casos {
		t.Setenv("PROXIES_DE_CONFIANZA", valor)
		if _, err := leerProxiesDeConfianza(); (err == nil) != valido {
			t.Errorf("PROXIES_DE_CONFIANZA=%q: err = %v", valor, err)
		}
	}
}

// Visitantes distintos detrás de Google ya no se bloquean entre sí
func TestUnAtacanteNoBloqueaATodos(t *testing.T) {
	conProxies(t, 1)
	python := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	})
	limite := limitarLogin(python)
	intento := func(ip string) int {
		r := httptest.NewRequest(http.MethodPost, "/api/login", strings.NewReader(`{"username":"admin","password":"x"}`))
		r.RemoteAddr = "169.254.1.1:8080" // siempre la misma: la de Google
		r.Header.Set("X-Forwarded-For", ip)
		w := httptest.NewRecorder()
		limite.ServeHTTP(w, r)
		return w.Code
	}
	for i := 0; i < maxPorUsuario; i++ {
		intento("198.51.100.66")
	}
	if codigo := intento("198.51.100.66"); codigo != http.StatusTooManyRequests {
		t.Fatalf("el atacante debía recibir 429, recibió %d", codigo)
	}
	if codigo := intento("203.0.113.7"); codigo != http.StatusUnauthorized {
		t.Fatalf("otra persona debía poder intentar (401), recibió %d", codigo)
	}
}
