package main

import (
	"fmt"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

// ===== Encabezados de seguridad =====

// politicaPagina (Content-Security-Policy) le dice al navegador de dónde puede
// cargar cosas la página. Si alguien lograra meter un <script> en un nombre de
// producto o en un mensaje del chat, el navegador no lo ejecutaría.
//   - scripts: solo script.js de aquí mismo (nada en línea ni de otros sitios)
//   - estilos y letras: los de aquí y Google Fonts
//   - fotos: las de img/ y las https:// que el Administrador ponga en un producto
//   - datos: solo de /api de aquí mismo
const politicaPagina = "default-src 'self'; " +
	"script-src 'self'; " +
	"style-src 'self' https://fonts.googleapis.com; " +
	"font-src https://fonts.gstatic.com; " +
	"img-src 'self' https: data:; " +
	"connect-src 'self'; " +
	"object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"

// conCabeceras agrega a todas las respuestas los encabezados que protegen al navegador
func conCabeceras(siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("X-Content-Type-Options", "nosniff") // un .jpg no se puede ejecutar como script
		h.Set("X-Frame-Options", "DENY")           // nadie mete la tienda dentro de su página (clickjacking)
		h.Set("Referrer-Policy", "same-origin")    // las direcciones de la tienda no se mandan a otros sitios
		if esHTTPS(r) {
			// El navegador recuerda por un año que la tienda va solo con HTTPS
			h.Set("Strict-Transport-Security", "max-age=31536000")
		}
		siguiente.ServeHTTP(w, r)
	})
}

// esHTTPS: si la petición llegó cifrada. Detrás de Google Cloud la conexión
// llega como HTTP desde Google, y él avisa con X-Forwarded-Proto: https
func esHTTPS(r *http.Request) bool {
	if r.TLS != nil {
		return true
	}
	if proxiesDeConfianza == 0 {
		return false
	}
	protocolos := strings.Split(r.Header.Get("X-Forwarded-Proto"), ",")
	return strings.TrimSpace(protocolos[len(protocolos)-1]) == "https"
}

// ===== CORS =====

// Qué OTROS sitios pueden llamar a la API desde el navegador. Desde que el
// Gateway entrega la página, ella no lo necesita (es el mismo sitio).
//   - CORS_ORIGENES="*": cualquiera (lo normal en tu computadora, para abrir
//     index.html con doble clic)
//   - CORS_ORIGENES="https://a.com,https://b.com": solo esos
//   - vacía: "*" en tu computadora y ninguno con ENTORNO=produccion
type configCORS struct {
	todos    bool
	origenes map[string]bool
}

func leerCORS(produccion bool) (configCORS, error) {
	texto := strings.TrimSpace(os.Getenv("CORS_ORIGENES"))
	if texto == "" {
		return configCORS{todos: !produccion}, nil
	}
	if texto == "*" {
		return configCORS{todos: true}, nil
	}
	c := configCORS{origenes: map[string]bool{}}
	for _, origen := range strings.Split(texto, ",") {
		origen = strings.TrimRight(strings.TrimSpace(origen), "/")
		if !strings.HasPrefix(origen, "https://") && !strings.HasPrefix(origen, "http://") {
			return c, fmt.Errorf("CORS_ORIGENES: %q debe empezar con https:// (ej. https://mitienda.com)", origen)
		}
		c.origenes[origen] = true
	}
	return c, nil
}

func (c configCORS) String() string {
	if c.todos {
		return "cualquier sitio (*)"
	}
	if len(c.origenes) == 0 {
		return "ningún otro sitio"
	}
	lista := []string{}
	for origen := range c.origenes {
		lista = append(lista, origen)
	}
	return strings.Join(lista, ", ")
}

func conCORS(c configCORS, siguiente http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origen := r.Header.Get("Origin")
		if c.todos {
			w.Header().Set("Access-Control-Allow-Origin", "*")
		} else if origen != "" && c.origenes[origen] {
			w.Header().Set("Access-Control-Allow-Origin", origen)
			w.Header().Add("Vary", "Origin")
		}
		if w.Header().Get("Access-Control-Allow-Origin") != "" {
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		}
		// La "pregunta previa" del navegador (preflight). Si el sitio no está
		// permitido, sin los encabezados de arriba el navegador no manda la petición
		if r.Method == http.MethodOptions && r.Header.Get("Access-Control-Request-Method") != "" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		siguiente.ServeHTTP(w, r)
	})
}

// ===== Límite de cuentas nuevas =====

// Cuántas veces se puede intentar crear una cuenta desde la misma IP por hora.
// Frena a quien crea cuentas en masa o prueba qué correos ya están registrados.
const (
	ventanaRegistro   = time.Hour
	maxRegistrosPorIP = 10
)

func limitarRegistro(siguiente http.Handler) http.Handler {
	l := nuevoLimitador(ventanaRegistro)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/usuarios" {
			siguiente.ServeHTTP(w, r)
			return
		}
		ip := ipDe(r)
		ahora := time.Now()
		l.mu.Lock()
		falta := l.espera(ip, maxRegistrosPorIP, ahora)
		if falta == 0 {
			l.sumar(ip, ahora) // aquí cuenta cada intento, salga bien o mal
		}
		l.mu.Unlock()
		if falta > 0 {
			w.Header().Set("Retry-After", strconv.Itoa(int(falta.Seconds())+1))
			responderJSON(w, http.StatusTooManyRequests, map[string]string{
				"detail": fmt.Sprintf("Demasiados registros desde tu conexión. Espera %d minutos y vuelve a intentar.", int(falta.Minutes())+1),
			})
			return
		}
		siguiente.ServeHTTP(w, r)
	})
}
