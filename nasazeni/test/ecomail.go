package main

import (
	"bufio"
	"io"
	"mime"
	"net"
	"net/http"
	"regexp"
	"strings"
	"time"
)

const odberPrefix = "/ecomail-test/odhlaseni/"

var odberToken = regexp.MustCompile("^[a-zA-Z0-9_-]{43}$")

func potvrzeniOdhlaseni(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Referrer-Policy", "no-referrer")
	token := strings.TrimPrefix(r.URL.EscapedPath(), odberPrefix)
	if !odberToken.MatchString(token) || r.URL.RawQuery != "" {
		http.NotFound(w, r)
		return
	}
	method := "GET"
	switch r.Method {
	case http.MethodGet, http.MethodHead:
	case http.MethodPost:
		r.Body = http.MaxBytesReader(w, r.Body, 4096)
		media, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
		if err == nil {
			switch media {
			case "multipart/form-data":
				err = r.ParseMultipartForm(4096)
			case "application/x-www-form-urlencoded":
				err = r.ParseForm()
			default:
				http.Error(w, "Neplatný typ formuláře", http.StatusUnsupportedMediaType)
				return
			}
		}
		values := r.PostForm["List-Unsubscribe"]
		if err != nil || len(r.PostForm) != 1 || len(values) != 1 || values[0] != "One-Click" || (r.MultipartForm != nil && len(r.MultipartForm.File) != 0) {
			http.Error(w, "Neplatné potvrzení odhlášení", http.StatusBadRequest)
			return
		}
		method = "POST"
	default:
		w.Header().Set("Allow", "GET, HEAD, POST")
		http.Error(w, "Nepodporovaná metoda", http.StatusMethodNotAllowed)
		return
	}
	conn, err := net.DialTimeout("unix", "/run/polarita-ecomail.sock", 5*time.Second)
	if err != nil {
		http.Error(w, "Odhlášení je dočasně nedostupné.", http.StatusServiceUnavailable)
		return
	}
	defer conn.Close()
	conn.SetDeadline(time.Now().Add(15 * time.Second))
	if _, err = io.WriteString(conn, method+" "+token+"\n"); err != nil {
		http.Error(w, "Přenos byl přerušen.", http.StatusServiceUnavailable)
		return
	}
	status, err := bufio.NewReader(io.LimitReader(conn, 8)).ReadString('\n')
	if err != nil || (status != "200\n" && status != "404\n") {
		http.Error(w, "Odhlášení je dočasně nedostupné.", http.StatusServiceUnavailable)
		return
	}
	if status == "404\n" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if method == "POST" {
		io.WriteString(w, `<!doctype html><html lang="cs"><meta charset="utf-8"><title>Odhlášení potvrzeno</title><h1>Odhlášení potvrzeno</h1><p>Další nabídky z tohoto seznamu už nedostanete.</p></html>`)
	} else if r.Method == http.MethodGet {
		io.WriteString(w, `<!doctype html><html lang="cs"><meta charset="utf-8"><title>Odhlásit odběr</title><h1>Servisní nabídky Polarita TEST</h1><form method="post"><button name="List-Unsubscribe" value="One-Click">Odhlásit odběr</button></form></html>`)
	}
}
