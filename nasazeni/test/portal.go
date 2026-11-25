// Testovací účet má přístup jen k výsledku přihlášení. Stav aplikací dokládají samostatné zkoušky.
package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"html/template"
	"io"
	"log"
	"net"
	"net/http"
	"net/netip"
	"os"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

const cookieName = "__Host-polarita-test"

var page = template.Must(template.New("portal").Parse(`<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ředitelství Polarity</title><style>
:root{font:110%/1.55 "Segoe UI",system-ui,sans-serif;color:#152a37;background:#f0f4f4}
body{margin:0}header{padding:1rem max(5vw,1rem);border-bottom:1px solid #bdccce;color:#294956}main{max-width:32rem;margin:8vh auto;padding:2rem}h1{font-size:clamp(2rem,6vw,3rem);line-height:1.12}label{display:block;margin:1rem 0 .3rem}input,button{font:inherit;padding:.65rem .8rem;border-radius:.3rem}input{width:100%;box-sizing:border-box;border:1px solid #778b90}button{margin:1rem 0;background:#15555c;color:white;border:0;cursor:pointer}small{color:#314f57}
</style><header>Polarita s.r.o.</header><main><h1>Ředitelství Polarity</h1>{{if .Signed}}<h2>Ověření přístupu</h2><p>Jste přihlášeni jako <strong>spravce</strong> v testovacím prostředí.</p>{{if .Web}}<p><a href="/web-test/">Otevřít firemní web a ceník</a></p>{{end}}{{if .Obchod}}<p><a href="{{.Obchod}}">Vyzkoušet nákup v e-shopu</a></p>{{end}}{{if .Eshop}}<p><a href="{{.Eshop}}">Otevřít správu e-shopu a kabelové bubny</a><br><small>Přihlaste se jako spravce@polarita.test svým testovacím heslem.</small></p>{{end}}{{if .Akademie}}<p><a href="{{.Akademie}}">Otevřít firemní Akademii</a></p>{{end}}{{if .Komise}}<p><a href="{{.Komise}}">Stáhnout protokol cvičné zkušební komise (PDF)</a></p>{{end}}{{if .Umami}}<p><a href="{{.Umami}}">Otevřít návštěvnost webu v Umami</a></p>{{end}}<p><a href="/konfigurator">Otevřít konfigurátor paušálu Elektro Správa</a></p>{{if .Vzor}}<p><a href="/vzory/predavaci-protokol.pdf">Stáhnout vzor předávacího protokolu s testovací pečetí (PDF)</a></p>{{end}}<p><a href="/identita/realms/polarita/account/">Otevřít můj účet v Keycloaku</a></p>{{if .Metadata}}<p><a href="/lhutnik-test/spisy">Spisy</a></p><p><a href="/lhutnik-test/">Testovací lhůtník</a></p>{{end}}{{if .Dohled}}<p><a href="/dohled">Stav firemních služeb</a></p>{{end}}{{if .Archiv}}<p><a href="{{.Archiv}}">Otevřít dokumentový archiv Paperless</a></p>{{end}}{{if .Tasks}}<p><a href="{{.Tasks}}">Otevřít úkolovník Vikunja</a></p>{{end}}{{if .Vault}}<p><a href="{{.Vault}}">Otevřít znalostní paměť</a></p>{{end}}{{if .Paperclip}}<p><a href="{{.Paperclip}}">Otevřít řízení firmy v Paperclipu</a></p>{{end}}{{if .Decisions}}<p><a href="{{.Decisions}}">Vyzkoušet rozhodnutí ve vzorovém spisu</a></p>{{end}}{{if .Chat}}<p><a href="{{.Chat}}">Otevřít týmový chat Zulip</a></p>{{end}}{{if .Git}}<p><a href="/git/user/oauth2/keycloak">Otevřít firemní Git</a></p>{{end}}<p><a href="/hesla/">Otevřít správce hesel Vaultwarden</a><br><small>Testovací účet spravce@polarita.test používá stejné heslo jako ředitelství.</small></p><form method="post" action="/odhlasit"><button>Odhlásit se</button></form>{{else}}<p>Přihlášení do testovacího prostředí</p>{{if .Error}}<p role="alert">{{.Error}}</p>{{end}}<form method="post" action="/prihlasit">{{if .Spis}}<input type="hidden" name="spis" value="{{.Spis}}">{{end}}<label for="u">Jméno</label><input id="u" name="username" autocomplete="username" required><label for="p">Heslo</label><input id="p" name="password" type="password" autocomplete="current-password" required><button>Přihlásit se</button></form>{{end}}</main></html>`))

const cestaDokladuAkademie = "/akademie-test/doklady/"
const slozkaDokladuAkademie = "/usr/local/share/polarita-akademie-doklady/"

var souborDokladuAkademie = regexp.MustCompile(`^[0-9a-f]{64}\.pdf$`)

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

const metadataPath = "/lhutnik-test/"

var cisloSpisu = regexp.MustCompile(`^POL-([1-9][0-9]{2}-)?[0-9]{4}-[0-9]{5}$`)

const metadataSocket = "/run/polarita-metadata.sock"

const metadataTimeout = 75 * time.Second

var metadataClient = privateClient(metadataSocket, metadataTimeout)
var sanonyClient = privateClient("/run/polarita-sanony.sock", 5*time.Minute)

func privateClient(socket string, timeout time.Duration) *http.Client {
	return &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{DialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			return (&net.Dialer{}).DialContext(ctx, "unix", socket)
		}},
		CheckRedirect: func(req *http.Request, via []*http.Request) error { return http.ErrUseLastResponse },
	}
}

var prijemPath = regexp.MustCompile(`^api/sanony/(POL-[0-9]{4}-[0-9]{5}/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$`)

func prijmiSanon(w http.ResponseWriter, r *http.Request, path string) {
	const limit = 64 << 20
	if r.Method != http.MethodPut {
		http.Error(w, "Nepodporovaná metoda", http.StatusMethodNotAllowed)
		return
	}
	if r.ContentLength <= 0 || r.ContentLength > limit {
		http.Error(w, "Zvolte neprázdné PDF do 64 MiB.", http.StatusRequestEntityTooLarge)
		return
	}
	if r.Header.Get("Content-Type") != "application/pdf" {
		http.Error(w, "Očekáván soubor PDF.", http.StatusUnsupportedMediaType)
		return
	}
	ctl := http.NewResponseController(w)
	until := time.Now().Add(5 * time.Minute)
	ctl.SetReadDeadline(until)
	ctl.SetWriteDeadline(until.Add(10 * time.Second))
	req, err := http.NewRequestWithContext(r.Context(), http.MethodPut, "http://localhost/"+path, http.MaxBytesReader(w, r.Body, limit))
	if err != nil {
		http.Error(w, "Neplatný požadavek", http.StatusBadRequest)
		return
	}
	req.ContentLength = r.ContentLength
	req.Header.Set("Content-Type", "application/pdf")
	res, err := sanonyClient.Do(req)
	if err != nil {
		http.Error(w, "Příjem je dočasně nedostupný.", http.StatusServiceUnavailable)
		return
	}
	defer res.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.WriteHeader(res.StatusCode)
	io.CopyN(w, res.Body, 4096)
}

func (p *portal) metadata(w http.ResponseWriter, r *http.Request) {
	cookie, err := r.Cookie(cookieName)
	if err == nil {
		p.lock.Lock()
		expiry := p.sessions[cookie.Value]
		p.lock.Unlock()
		if time.Now().Before(expiry) {
			p.serveMetadata(w, r)
			return
		}
	}
	if r.Method == http.MethodGet {
		if spis := r.URL.Query().Get("spis"); r.URL.Path == metadataPath+"spisy" && cisloSpisu.MatchString(spis) {
			http.Redirect(w, r, "/?spis="+spis, http.StatusSeeOther)
			return
		}
		http.Redirect(w, r, "/", http.StatusSeeOther)
	} else {
		http.Error(w, "Přihlaste se do ředitelství.", http.StatusUnauthorized)
	}
}

func (p *portal) serveMetadata(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		if r.Method != http.MethodPost && r.Method != http.MethodPut {
			http.Error(w, "Nepodporovaná metoda", http.StatusMethodNotAllowed)
			return
		}
		if r.Header.Get("Origin") != "https://"+r.Host {
			http.Error(w, "Cizí původ požadavku", http.StatusForbidden)
			return
		}
	}
	path := strings.TrimPrefix(r.URL.EscapedPath(), metadataPath)
	if match := prijemPath.FindStringSubmatch(path); match != nil {
		prijmiSanon(w, r, match[1])
		return
	}
	req, err := http.NewRequestWithContext(r.Context(), r.Method, "http://localhost/"+path, nil)
	if err != nil {
		http.Error(w, "Neplatná cesta", http.StatusBadRequest)
		return
	}
	if r.Method != http.MethodGet {
		body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
		if err != nil {
			http.Error(w, "Neplatné tělo", http.StatusBadRequest)
			return
		}
		req.Body = io.NopCloser(bytes.NewReader(body))
		req.ContentLength = int64(len(body))
		req.Header.Set("Content-Type", r.Header.Get("Content-Type"))
		if tag := r.Header.Get("If-Match"); tag != "" {
			req.Header.Set("If-Match", tag)
		}
	}
	// Čas pro zápis odpovědi zahrnuje i čekání na lokální databázi.
	http.NewResponseController(w).SetWriteDeadline(time.Now().Add(metadataTimeout + 10*time.Second))
	res, err := metadataClient.Do(req)
	if err != nil {
		http.Error(w, "Lhůtník je dočasně nedostupný.", http.StatusServiceUnavailable)
		return
	}
	defer res.Body.Close()
	if r.Method == http.MethodGet && (strings.HasPrefix(path, "api/spisy/") || strings.HasPrefix(path, "api/kniha/") || strings.HasPrefix(path, "api/sanony/")) {
		if url := archiveURL(); url != "" {
			w.Header().Set("X-Polarita-Archiv", url)
		}
	}
	for _, name := range []string{"Content-Type", "ETag"} {
		if value := res.Header.Get(name); value != "" {
			w.Header().Set(name, value)
		}
	}
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
	w.WriteHeader(res.StatusCode)
	io.Copy(w, res.Body)
}

const archiveFile = "/usr/local/share/polarita-paperless-url"

var akademieAddress = regexp.MustCompile(`^https://[a-z0-9.-]+\.ts\.net:8451/my/$`)
var eshopAddress = regexp.MustCompile(`^https://[a-z0-9.-]+\.ts\.net:8450/app/$`)
var umamiAddress = regexp.MustCompile(`^https://[a-z0-9.-]+\.ts\.net:8449/$`)

var archiveAddress = regexp.MustCompile(`^https://[a-z0-9.-]+\.ts\.net:8448/$`)

func archiveURL() string {
	address, _ := os.ReadFile(archiveFile)
	url := strings.TrimSpace(string(address))
	if archiveAddress.MatchString(url) {
		return url
	}
	return ""
}

const webRoot = "/usr/local/share/polarita-web/current"

type portalView struct {
	Akademie  string
	Komise    string
	Eshop     string
	Obchod    string
	Umami     string
	Web       bool
	Archiv    string
	Spis      string
	Tasks     string
	Vault     string
	Paperclip string
	Decisions string
	Chat      string
	Dohled    bool
	Metadata  bool
	Git       bool
	Vzor      bool
	Signed    bool
	Error     string
}

func overview() portalView {
	_, webErr := os.Stat(webRoot + "/index.html")
	_, vzorErr := os.Stat(vzor)
	_, monitorErr := os.Stat(monitorFile)
	metadataInfo, metadataErr := os.Stat(metadataSocket)
	_, gitErr := os.Stat("/usr/local/share/polarita-gitea-oidc.ok")
	tasks, _ := os.ReadFile("/usr/local/share/polarita-vikunja-url")
	vaultURL, _ := os.ReadFile("/usr/local/share/polarita-silverbullet-url")
	chat, _ := os.ReadFile("/usr/local/share/polarita-zulip-url")
	orchestrator, _ := os.ReadFile("/usr/local/share/polarita-paperclip-url")
	decisions, _ := os.ReadFile("/usr/local/share/polarita-decisions-url")
	umami, _ := os.ReadFile("/usr/local/share/polarita-umami-url")
	umamiURL := strings.TrimSpace(string(umami))
	if !umamiAddress.MatchString(umamiURL) {
		umamiURL = ""
	}
	akademie, _ := os.ReadFile("/usr/local/share/polarita-akademie-url")
	akademieURL := strings.TrimSpace(string(akademie))
	if !akademieAddress.MatchString(akademieURL) {
		akademieURL = ""
	}
	eshop, _ := os.ReadFile("/usr/local/share/polarita-medusa-url")
	eshopURL := strings.TrimSpace(string(eshop))
	if !eshopAddress.MatchString(eshopURL) {
		eshopURL = ""
	}
	obchodURL := ""
	if eshopURL != "" {
		if _, err := os.Stat("/usr/local/share/polarita-obchod-overen"); err == nil {
			obchodURL = strings.TrimSuffix(eshopURL, "/app/") + "/obchod/"
		}
	}
	komise := ""
	if index, err := os.ReadFile(slozkaDokladuAkademie + "komise"); err == nil {
		if soubor := strings.TrimSpace(string(index)); souborDokladuAkademie.MatchString(soubor) {
			komise = cestaDokladuAkademie + soubor
		}
	}
	return portalView{Komise: komise, Akademie: akademieURL, Obchod: obchodURL, Eshop: eshopURL, Umami: umamiURL, Web: webErr == nil, Archiv: archiveURL(), Tasks: strings.TrimSpace(string(tasks)), Vault: strings.TrimSpace(string(vaultURL)), Metadata: metadataErr == nil && metadataInfo.Mode()&os.ModeSocket != 0, Decisions: strings.TrimSpace(string(decisions)), Paperclip: strings.TrimSpace(string(orchestrator)), Chat: strings.TrimSpace(string(chat)), Dohled: monitorErr == nil, Signed: true, Vzor: vzorErr == nil, Git: gitErr == nil}
}

func (p *portal) login(username, password, previous string) (string, int) {
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
	if len(p.failures) >= 10 {
		return "", http.StatusTooManyRequests
	}
	digest := sha256.Sum256([]byte(password))
	if subtle.ConstantTimeCompare(digest[:], p.digest[:]) != 1 || username != "spravce" {
		p.failures = append(p.failures, now)
		return "", http.StatusUnauthorized
	}
	var b [32]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", http.StatusInternalServerError
	}
	token := hex.EncodeToString(b[:])
	delete(p.sessions, previous)
	p.sessions[token] = now.Add(2 * time.Hour)
	return token, http.StatusOK
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
	if strings.HasPrefix(r.URL.Path, odberPrefix) {
		potvrzeniOdhlaseni(w, r)
		return
	}
	if strings.HasPrefix(r.URL.Path, metadataPath) {
		p.metadata(w, r)
		return
	}
	var token string
	if c, err := r.Cookie(cookieName); err == nil {
		token = c.Value
	}
	p.lock.Lock()
	signed := time.Now().Before(p.sessions[token])
	p.lock.Unlock()
	var view portalView
	switch {
	case r.URL.Path == "/" && r.Method == "GET":
		if spis := r.URL.Query().Get("spis"); cisloSpisu.MatchString(spis) {
			view.Spis = spis
			if signed {
				http.Redirect(w, r, metadataPath+"spisy?spis="+spis, http.StatusSeeOther)
				return
			}
		}
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
	case strings.HasPrefix(r.URL.Path, cestaDokladuAkademie) && (r.Method == "GET" || r.Method == "HEAD"):
		if !signed {
			http.Redirect(w, r, "/", http.StatusSeeOther)
			return
		}
		file := strings.TrimPrefix(r.URL.Path, cestaDokladuAkademie)
		if !souborDokladuAkademie.MatchString(file) {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/pdf")
		w.Header().Set("Content-Disposition", `attachment; filename="akademie-`+file+`"`)
		http.ServeFile(w, r, slozkaDokladuAkademie+file)
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
	case (r.URL.Path == "/web-test/kalkulacka-svj/" || r.URL.Path == "/web-test/kalkulacka-svj/podklad.pdf") && r.Method == http.MethodPost:
		if !signed {
			http.Error(w, "Přihlaste se do ředitelství.", http.StatusUnauthorized)
			return
		}
		kalkulackaSVJ(w, r)
		return
	case strings.HasPrefix(r.URL.Path, "/web-test/") && (r.Method == "GET" || r.Method == "HEAD"):
		if !signed {
			http.Redirect(w, r, "/", http.StatusSeeOther)
			return
		}
		// Zpřístupni jen veřejné soubory ověřeného sestavení Astro.
		files := map[string]string{"/web-test/": "index.html", "/web-test/kalkulacka-svj/": "kalkulacka-svj/index.html", "/web-test/prevzeti-sanonu/": "prevzeti-sanonu/index.html", "/web-test/llms.txt": "llms.txt", "/web-test/souhlas.js": "souhlas.js", "/web-test/reklama-test.js": "reklama-test.js"}
		name, ok := files[r.URL.Path]
		if !ok {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
		w.Header().Set("X-Robots-Tag", "noindex, nofollow")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		http.ServeFile(w, r, webRoot+"/"+name)
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
		r.Body = http.MaxBytesReader(w, r.Body, 4096)
		if err := r.ParseForm(); err != nil {
			http.Error(w, "Chybný formulář", 400)
			return
		}
		if spis := r.PostForm.Get("spis"); cisloSpisu.MatchString(spis) {
			view.Spis = spis
		}
		newToken, status := p.login(r.PostForm.Get("username"), r.PostForm.Get("password"), token)
		switch status {
		case http.StatusTooManyRequests:
			w.Header().Set("Retry-After", "60")
			http.Error(w, "Zkuste to za minutu.", status)
			return
		case http.StatusInternalServerError:
			http.Error(w, "Přihlášení selhalo", status)
			return
		case http.StatusUnauthorized:
			view.Error = "Jméno nebo heslo nesouhlasí."
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.WriteHeader(status)
		default:
			http.SetCookie(w, &http.Cookie{Name: cookieName, Value: newToken, Path: "/", Secure: true, HttpOnly: true, SameSite: http.SameSiteStrictMode, MaxAge: 7200})
			next := "/prehled"
			if view.Spis != "" {
				next = metadataPath + "spisy?spis=" + view.Spis
			}
			http.Redirect(w, r, next, http.StatusSeeOther)
			return
		}
	case r.URL.Path == "/odhlasit" && r.Method == "POST":
		p.lock.Lock()
		delete(p.sessions, token)
		p.lock.Unlock()
		http.SetCookie(w, &http.Cookie{Name: cookieName, Path: "/", MaxAge: -1, Secure: true, HttpOnly: true, SameSite: http.SameSiteStrictMode})
		http.Redirect(w, r, "/", 303)
		return
	default:
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if signed && r.Method == http.MethodGet {
		view = overview()
	}
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
	server := &http.Server{Addr: "0.0.0.0:8080", Handler: p, ReadTimeout: 8 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 8192}
	log.Fatal(server.ListenAndServe())
}
