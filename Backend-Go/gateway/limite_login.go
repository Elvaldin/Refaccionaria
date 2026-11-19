package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Límite de intentos de inicio de sesión: frena a quien prueba muchas
// contraseñas. Solo cuenta los intentos FALLIDOS (401) en 15 minutos:
//   - 5 con el mismo usuario desde la misma IP
//   - 20 desde la misma IP, sin importar el usuario
//
// Al pasarse, responde 429 hasta que terminen esos 15 minutos.
// Entrar bien borra los fallos de ese usuario desde esa IP.
const (
	ventanaLogin  = 15 * time.Minute
	maxPorUsuario = 5
	maxPorIP      = 20
)

type intentos struct {
	fallos int
	desde  time.Time // cuándo empezó a contar
}

type limitador struct {
	mu        sync.Mutex
	registros map[string]*intentos
	ventana   time.Duration // cuánto tiempo se recuerdan los intentos
}

// nuevoLimitador crea un limitador y cada 5 minutos borra lo que ya venció,
// para que el mapa no crezca sin fin
func nuevoLimitador(ventana time.Duration) *limitador {
	l := &limitador{registros: map[string]*intentos{}, ventana: ventana}
	go func() {
		for range time.Tick(5 * time.Minute) {
			l.mu.Lock()
			l.limpiar(time.Now())
			l.mu.Unlock()
		}
	}()
	return l
}

// espera regresa cuánto falta para que esa clave pueda volver a intentar (0 = puede ya)
func (l *limitador) espera(clave string, maximo int, ahora time.Time) time.Duration {
	r, ok := l.registros[clave]
	if !ok || ahora.Sub(r.desde) > l.ventana || r.fallos < maximo {
		return 0
	}
	return l.ventana - ahora.Sub(r.desde)
}

func (l *limitador) sumar(clave string, ahora time.Time) {
	r, ok := l.registros[clave]
	if !ok || ahora.Sub(r.desde) > l.ventana {
		l.registros[clave] = &intentos{fallos: 1, desde: ahora}
		return
	}
	r.fallos++
}

// limpiar borra lo que ya venció, para que el mapa no crezca sin fin
func (l *limitador) limpiar(ahora time.Time) {
	for clave, r := range l.registros {
		if ahora.Sub(r.desde) > l.ventana {
			delete(l.registros, clave)
		}
	}
}

// grabadorEstado deja pasar la respuesta y apunta qué código regresó Python
type grabadorEstado struct {
	http.ResponseWriter
	estado int
}

func (g *grabadorEstado) WriteHeader(codigo int) {
	g.estado = codigo
	g.ResponseWriter.WriteHeader(codigo)
}

// proxiesDeConfianza: cuántas direcciones agrega NUESTRA infraestructura al final
// del encabezado X-Forwarded-For (variable PROXIES_DE_CONFIANZA).
//   - 0 (en tu computadora y en Docker): no hay proxy; se usa la IP de la conexión.
//   - Detrás de Google Cloud Run o de un balanceador, la conexión siempre viene
//     de Google (la misma IP para todos) y la IP real del visitante va en
//     X-Forwarded-For. Lo que el visitante escriba en ese encabezado queda a la
//     izquierda, por eso se cuenta desde la derecha y no se le cree al primero.
var proxiesDeConfianza = 0

// leerProxiesDeConfianza lee PROXIES_DE_CONFIANZA (vacía = 0)
func leerProxiesDeConfianza() (int, error) {
	texto := strings.TrimSpace(os.Getenv("PROXIES_DE_CONFIANZA"))
	if texto == "" {
		return 0, nil
	}
	n, err := strconv.Atoi(texto)
	if err != nil || n < 0 || n > 5 {
		return 0, fmt.Errorf("PROXIES_DE_CONFIANZA debe ser un número de 0 a 5 (llegó %q)", texto)
	}
	return n, nil
}

// ipDe regresa la IP de quien hace la petición, la que se usa para contar intentos
func ipDe(r *http.Request) string {
	if proxiesDeConfianza > 0 {
		var direcciones []string
		for _, encabezado := range r.Header.Values("X-Forwarded-For") {
			for _, parte := range strings.Split(encabezado, ",") {
				direcciones = append(direcciones, strings.TrimSpace(parte))
			}
		}
		// La que puso el primer proxy nuestro: la N-ésima contando desde la derecha
		if i := len(direcciones) - proxiesDeConfianza; i >= 0 {
			if ip := net.ParseIP(direcciones[i]); ip != nil {
				return agruparIP(ip)
			}
		}
		// Si no viene bien, se usa la de la conexión (es mejor que nada)
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		host = r.RemoteAddr
	}
	if ip := net.ParseIP(host); ip != nil {
		return agruparIP(ip)
	}
	return host
}

// agruparIP: con IPv6 cada casa recibe millones de direcciones (un bloque /64),
// así que se cuenta por bloque; si no, bastaría cambiar de dirección para seguir probando
func agruparIP(ip net.IP) string {
	if ip.To4() != nil {
		return ip.To4().String()
	}
	return ip.Mask(net.CIDRMask(64, 128)).String() + "/64"
}

func limitarLogin(siguiente http.Handler) http.Handler {
	l := nuevoLimitador(ventanaLogin)

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/login" {
			siguiente.ServeHTTP(w, r)
			return
		}

		// Se lee el usuario del cuerpo y se vuelve a dejar el cuerpo como estaba para Python
		cuerpo, err := io.ReadAll(r.Body)
		if err != nil {
			responderJSON(w, http.StatusRequestEntityTooLarge, map[string]string{"detail": "La petición es demasiado grande."})
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(cuerpo))
		var datos struct {
			Username string `json:"username"`
		}
		json.Unmarshal(cuerpo, &datos) // si no es JSON válido, Python contesta 422

		ip := ipDe(r)
		claveUsuario := ip + "|" + strings.ToLower(strings.TrimSpace(datos.Username))
		ahora := time.Now()

		l.mu.Lock()
		falta := max(l.espera(claveUsuario, maxPorUsuario, ahora), l.espera(ip, maxPorIP, ahora))
		l.mu.Unlock()
		if falta > 0 {
			minutos := int(falta.Minutes()) + 1
			w.Header().Set("Retry-After", strconv.Itoa(int(falta.Seconds())+1))
			responderJSON(w, http.StatusTooManyRequests, map[string]string{
				"detail": fmt.Sprintf("Demasiados intentos fallidos. Espera %d minutos y vuelve a intentar.", minutos),
			})
			return
		}

		grabador := &grabadorEstado{ResponseWriter: w, estado: http.StatusOK}
		siguiente.ServeHTTP(grabador, r)

		l.mu.Lock()
		switch grabador.estado {
		case http.StatusUnauthorized:
			l.sumar(claveUsuario, ahora)
			l.sumar(ip, ahora)
		case http.StatusOK:
			delete(l.registros, claveUsuario)
		}
		l.mu.Unlock()
	})
}
