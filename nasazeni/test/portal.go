// Testovací účet má přístup jen k výsledku přihlášení. Stav aplikací dokládají samostatné zkoušky.
package main

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"html/template"
	"log"
	"net/http"
	"net/netip"
	"os"
	"sort"
	"strings"
	"sync"
	"time"
)

const cookieName = "__Host-polarita-test"

var page = template.Must(template.New("portal").Parse(`<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ředitelství Polarity</title><style>
:root{font:110%/1.55 "Segoe UI",system-ui,sans-serif;color:#152a37;background:#f0f4f4}
body{margin:0}header{padding:1rem max(5vw,1rem);border-bottom:1px solid #bdccce;color:#294956}main{max-width:32rem;margin:8vh auto;padding:2rem}h1{font-size:clamp(2rem,6vw,3rem);line-height:1.12}label{display:block;margin:1rem 0 .3rem}input,button{font:inherit;padding:.65rem .8rem;border-radius:.3rem}input{width:100%;box-sizing:border-box;border:1px solid #778b90}button{margin:1rem 0;background:#15555c;color:white;border:0;cursor:pointer}small{color:#314f57}
</style><header>Polarita s.r.o.</header><main><h1>Ředitelství Polarity</h1>{{if .Signed}}<h2>Ověření přístupu</h2><p>Jste přihlášeni jako <strong>spravce</strong> v testovacím prostředí.</p><p><a href="/konfigurator">Otevřít konfigurátor paušálu Elektro Správa</a></p>{{if .Vzor}}<p><a href="/vzory/predavaci-protokol.pdf">Stáhnout vzor předávacího protokolu s testovací pečetí (PDF)</a></p>{{end}}<p><a href="/identita/realms/polarita/account/">Otevřít můj účet v Keycloaku</a></p>{{if .Dohled}}<p><a href="/dohled">Stav firemních služeb</a></p>{{end}}{{if .Git}}<p><a href="/git/user/oauth2/keycloak">Otevřít firemní Git</a></p>{{end}}<p><a href="/hesla/">Otevřít správce hesel Vaultwarden</a><br><small>Testovací účet spravce@polarita.test používá stejné heslo jako ředitelství.</small></p><form method="post" action="/odhlasit"><button>Odhlásit se</button></form>{{else}}<p>Přihlášení do testovacího prostředí</p>{{if .Error}}<p role="alert">{{.Error}}</p>{{end}}<form method="post" action="/prihlasit"><label for="u">Jméno</label><input id="u" name="username" autocomplete="username" required><label for="p">Heslo</label><input id="p" name="password" type="password" autocomplete="current-password" required><button>Přihlásit se</button></form>{{end}}</main></html>`))

const vzor = "/usr/local/share/predavaci-protokol-test.pdf"

const monitorFile = "/usr/local/share/polarita-dohled.json"

var monitorPage = template.Must(template.New("dohled").Parse(`<!doctype html>
<html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stav služeb | Ředitelství Polarity</title>
<style>:root{font:105%/1.5 "Segoe UI",system-ui,sans-serif;color:#152a37;background:#f0f4f4}main{max-width:56rem;margin:4vh auto;padding:1rem}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:.55rem;border-bottom:1px solid #bdccce}caption{text-align:left;font-weight:600}a{color:#15555c}</style>
<main><a href="/prehled">Zpět na ředitelství</a><h1>Stav firemních služeb</h1>
<table><caption>Checkmk · polarita-hq</caption><thead><tr><th>Služba</th><th>Stav</th><th>Poslední měření (UTC)</th></tr></thead>
<tbody>{{range .}}<tr><td>{{.Name}}</td><td>{{.Status}}</td><td>{{.When}}</td></tr>{{end}}</tbody></table></main></html>`))

func showMonitor(w http.ResponseWriter) {
	raw, err := os.ReadFile(monitorFile)
	var samples map[string]struct {
		State int   `json:"stav"`
		Time  int64 `json:"cas"`
	}
	if err != nil || json.Unmarshal(raw, &samples) != nil || len(samples) == 0 {
		http.Error(w, "Výsledky Checkmk zatím nejsou dostupné.", http.StatusServiceUnavailable)
		return
	}
	type row struct{ Name, Status, When string }
	rows := make([]row, 0, len(samples))
	states := []string{"V provozu", "Upozornění", "Výpadek", "Neznámý"}
	for name, sample := range samples {
		measured := time.Unix(sample.Time, 0).UTC()
		status := "Čeká na aktuální měření"
		when := "Dosud neproběhlo"
		if sample.Time > 0 {
			when = measured.Format("02. 01. 2006 15:04:05")
			age := time.Since(measured)
			if age >= 0 && age <= 5*time.Minute && sample.State >= 0 && sample.State < len(states) {
				status = states[sample.State]
			}
		}
		rows = append(rows, row{strings.TrimPrefix(name, "Polarita "), status, when})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].Name < rows[j].Name })
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := monitorPage.Execute(w, rows); err != nil {
		log.Print("Přenos stavu služeb byl přerušen")
	}
}

type portal struct {
	digest   [32]byte
	lock     sync.Mutex
	sessions map[string]time.Time
	failures []time.Time
}

func (p *portal) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	peer, err := netip.ParseAddrPort(r.RemoteAddr)
	if err != nil || !(peer.Addr().IsLoopback() || peer.Addr() == netip.MustParseAddr("10.239.31.10")) {
		http.Error(w, "Přístup vede přes firemní proxy", http.StatusForbidden)
		return
	}
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
	w.Header().Set("Referrer-Policy", "same-origin")
	if r.Method == "POST" && r.Header.Get("Origin") != "" && r.Header.Get("Origin") != "https://"+r.Host {
		http.Error(w, "Cizí původ požadavku", 403)
		return
	}
	p.lock.Lock()
	defer p.lock.Unlock()
	now := time.Now()
	for token, end := range p.sessions {
		if !end.After(now) {
			delete(p.sessions, token)
		}
	}
	for len(p.failures) > 0 && now.Sub(p.failures[0]) > time.Minute {
		p.failures = p.failures[1:]
	}
	token := ""
	if c, err := r.Cookie(cookieName); err == nil {
		token = c.Value
	}
	_, signed := p.sessions[token]
	_, vzorErr := os.Stat(vzor)
	_, monitorErr := os.Stat(monitorFile)
	_, gitErr := os.Stat("/usr/local/share/polarita-gitea-oidc.ok")
	view := struct {
		Dohled bool
		Git    bool
		Vzor   bool
		Signed bool
		Error  string
	}{Dohled: monitorErr == nil, Signed: signed, Vzor: vzorErr == nil, Git: gitErr == nil}
	switch {
	case r.URL.Path == "/" && r.Method == "GET":
	case r.URL.Path == "/prehled" && r.Method == "GET":
		if !signed {
			http.Redirect(w, r, "/", http.StatusSeeOther)
			return
		}
	case r.URL.Path == "/dohled" && r.Method == "GET":
		if !signed {
			http.Redirect(w, r, "/", http.StatusSeeOther)
			return
		}
		showMonitor(w)
		return
	case r.URL.Path == "/vzory/predavaci-protokol.pdf" && r.Method == "GET":
		if !signed {
			http.Redirect(w, r, "/", http.StatusSeeOther)
			return
		}
		w.Header().Set("Content-Type", "application/pdf")
		w.Header().Set("Content-Disposition", `attachment; filename="predavaci-protokol-test.pdf"`)
		http.ServeFile(w, r, vzor)
		return
	case r.URL.Path == "/konfigurator" && r.Method == "GET":
		if !signed {
			http.Redirect(w, r, "/", http.StatusSeeOther)
			return
		}
		w.Header().Set("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'")
		http.ServeFile(w, r, "/usr/local/share/konfigurator.html")
		return
	case r.URL.Path == "/prihlasit" && r.Method == "POST":
		if len(p.failures) >= 10 {
			w.Header().Set("Retry-After", "60")
			http.Error(w, "Zkuste to za minutu.", 429)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 4096)
		if err := r.ParseForm(); err != nil {
			http.Error(w, "Chybný formulář", 400)
			return
		}
		digest := sha256.Sum256([]byte(r.PostForm.Get("password")))
		if subtle.ConstantTimeCompare(digest[:], p.digest[:]) != 1 || r.PostForm.Get("username") != "spravce" {
			p.failures = append(p.failures, now)
			view.Error = "Jméno nebo heslo nesouhlasí."
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.WriteHeader(401)
		} else {
			var b [32]byte
			if _, err := rand.Read(b[:]); err != nil {
				http.Error(w, "Přihlášení selhalo", 500)
				return
			}
			delete(p.sessions, token)
			token = hex.EncodeToString(b[:])
			p.sessions[token] = now.Add(2 * time.Hour)
			http.SetCookie(w, &http.Cookie{Name: cookieName, Value: token, Path: "/", Secure: true, HttpOnly: true, SameSite: http.SameSiteStrictMode, MaxAge: 7200})
			http.Redirect(w, r, "/prehled", 303)
			return
		}
	case r.URL.Path == "/odhlasit" && r.Method == "POST":
		delete(p.sessions, token)
		http.SetCookie(w, &http.Cookie{Name: cookieName, Path: "/", MaxAge: -1, Secure: true, HttpOnly: true, SameSite: http.SameSiteStrictMode})
		http.Redirect(w, r, "/", 303)
		return
	default:
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := page.Execute(w, view); err != nil {
		log.Print("Chyba při odesílání stránky")
	}
}

func main() {
	raw, err := os.ReadFile("/etc/polarita-test.sha256")
	if err != nil {
		log.Fatal(err)
	}
	b, err := hex.DecodeString(strings.TrimSpace(string(raw)))
	if err != nil || len(b) != 32 {
		log.Fatal("Neplatný otisk hesla")
	}
	p := &portal{sessions: make(map[string]time.Time)}
	copy(p.digest[:], b)
	server := &http.Server{Addr: "0.0.0.0:8080", Handler: p, ReadTimeout: 8 * time.Second, WriteTimeout: 8 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 8192}
	log.Fatal(server.ListenAndServe())
}
