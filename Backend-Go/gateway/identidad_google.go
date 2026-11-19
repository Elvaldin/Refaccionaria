package main

// En Google Cloud Run los 5 microservicios se publican SIN acceso libre
// (--no-allow-unauthenticated): Google solo deja pasar a quien demuestre quién
// es con un "token de identidad". Con IDENTIDAD_GOOGLE=si, el Gateway pide ese
// token al servidor de metadatos de Google (solo existe dentro de Google Cloud)
// y lo manda en X-Serverless-Authorization. Se usa ese encabezado, y no
// Authorization, porque Authorization ya lleva el token de sesión del usuario.

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// Dónde se pide el token (se cambia solo en las pruebas)
var urlMetadatos = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"

// Los tokens de Google duran 1 hora: se guardan 55 minutos y se piden de nuevo
const duracionToken = 55 * time.Minute

type tokenGuardado struct {
	valor string
	vence time.Time
}

type identidadGoogle struct {
	mu      sync.Mutex
	tokens  map[string]tokenGuardado // uno por microservicio (por su URL)
	cliente http.Client
}

func nuevaIdentidadGoogle() *identidadGoogle {
	return &identidadGoogle{tokens: map[string]tokenGuardado{}, cliente: http.Client{Timeout: 3 * time.Second}}
}

// token regresa un token para hablar con el microservicio de esa URL
func (g *identidadGoogle) token(audiencia string) (string, error) {
	g.mu.Lock()
	defer g.mu.Unlock()
	if t, ok := g.tokens[audiencia]; ok && time.Now().Before(t.vence) {
		return t.valor, nil
	}
	peticion, _ := http.NewRequest(http.MethodGet, urlMetadatos+"?audience="+url.QueryEscape(audiencia), nil)
	peticion.Header.Set("Metadata-Flavor", "Google")
	respuesta, err := g.cliente.Do(peticion)
	if err != nil {
		return "", fmt.Errorf("no se pudo pedir el token de identidad a Google: %w", err)
	}
	defer respuesta.Body.Close()
	cuerpo, _ := io.ReadAll(io.LimitReader(respuesta.Body, 16<<10))
	if respuesta.StatusCode != http.StatusOK || len(cuerpo) == 0 {
		return "", fmt.Errorf("el servidor de metadatos contestó %d", respuesta.StatusCode)
	}
	valor := strings.TrimSpace(string(cuerpo))
	g.tokens[audiencia] = tokenGuardado{valor: valor, vence: time.Now().Add(duracionToken)}
	return valor, nil
}

// transporteConIdentidad agrega el token a cada petición que va al microservicio.
// Si no se puede conseguir, la petición no se manda y el Gateway contesta 502.
type transporteConIdentidad struct {
	base      http.RoundTripper
	identidad *identidadGoogle
	audiencia string
}

func (t transporteConIdentidad) RoundTrip(r *http.Request) (*http.Response, error) {
	token, err := t.identidad.token(t.audiencia)
	if err != nil {
		return nil, err
	}
	copia := r.Clone(r.Context())
	copia.Header.Set("X-Serverless-Authorization", "Bearer "+token)
	return t.base.RoundTrip(copia)
}
