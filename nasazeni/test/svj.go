package main

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/json"
	"fmt"
	"html/template"
	"net/http"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"
)

//go:embed web/vysledek-svj.html
var svjHTML string

//go:embed web/podklad-svj.typ
var svjTypst string

var svjVysledek = template.Must(template.New("svj").Parse(svjHTML))
var svjCena = regexp.MustCompile(`^[0-9]{1,3}([.,][0-9]{1,2})?$`)
var svjCele = regexp.MustCompile(`^[0-9]{1,8}$`)
var svjTisk = make(chan struct{}, 1)

type modelSVJ struct {
	Subjekt, Revize, Spravce, Stav, RevizniKrok, Riziko, Zdroj string
	Kwh, Cena, Procent, Energie, Uspora                        string
}

func celaHodnota(s string, max int64) (int64, bool) {
	if !svjCele.MatchString(s) {
		return 0, false
	}
	n, err := strconv.ParseInt(s, 10, 64)
	return n, err == nil && n <= max
}

func spocitejSVJ(r *http.Request) (d modelSVJ, ok bool) {
	if len(r.PostForm) != 5 {
		return
	}
	for _, key := range []string{"subjekt", "revize", "kwh", "cena", "procent"} {
		if len(r.PostForm[key]) != 1 {
			return
		}
	}
	d.Subjekt, d.Revize = r.PostForm.Get("subjekt"), r.PostForm.Get("revize")
	d.Zdroj = "https://suip.gov.cz/web/oip03/informace-z-bozp-a-vtz/-/asset_publisher/pXSdESbU34gE/content/372604-10/20142"
	switch d.Subjekt {
	case "svj":
		d.Spravce = "SVJ bez zaměstnanců"
		d.Riziko = "Výbor by měl doložit péči o společné části domu. Projděte podmínky pojistné smlouvy, odpovědnost za škodu a oprávnění dodavatele revize."
	case "firma", "svj-pracoviste":
		d.Spravce = "Firma nebo podnikatel"
		if d.Subjekt == "svj-pracoviste" {
			d.Spravce = "SVJ se zaměstnanci"
		}
		d.Riziko = "Ověřte bezpečnost pracoviště a oprávnění dodavatele. SÚIP uvádí horní hranici pokuty 2 000 000 Kč za provádění montáže, opravy, revize či zkoušky vyhrazeného zařízení bez příslušného oprávnění. Konkrétní postih závisí na zjištěném přestupku."
	default:
		return
	}
	switch d.Revize {
	case "aktualni":
		d.Stav = "Revize doložena"
		d.RevizniKrok = "Ověřte odstranění závad uvedených ve zprávě a evidujte datum další revize."
	case "po-lhute":
		d.Stav = "Termín revize uplynul"
		d.RevizniKrok = "Projednejte stav zařízení s revizním technikem a dohodněte další postup a termín."
	case "nezjisteno":
		d.Stav = "Revize nedoložena"
		d.RevizniKrok = "Dohledejte revizní zprávu a ověřte s revizním technikem rozsah zařízení a termín další revize."
	default:
		return
	}
	kwh, valid := celaHodnota(r.PostForm.Get("kwh"), 10000000)
	pct, validPct := celaHodnota(r.PostForm.Get("procent"), 100)
	cena := r.PostForm.Get("cena")
	if !valid || !validPct || !svjCena.MatchString(cena) {
		return
	}
	kc, hal, _ := strings.Cut(strings.ReplaceAll(cena, ",", "."), ".")
	koruny, _ := strconv.ParseInt(kc, 10, 64)
	halere, _ := strconv.ParseInt((hal + "00")[:2], 10, 64)
	jednotka := koruny*100 + halere
	if jednotka < 1 || jednotka > 10000 {
		return
	}
	d.Kwh, d.Procent = strconv.FormatInt(kwh, 10), strconv.FormatInt(pct, 10)
	d.Cena = fmt.Sprintf("%d,%02d", koruny, halere)
	energie := kwh * pct
	d.Energie = strings.TrimRight(strings.TrimRight(fmt.Sprintf("%d,%02d", energie/100, energie%100), "0"), ",")
	d.Uspora = strconv.FormatInt((energie*jednotka+5000)/10000, 10)
	return d, true
}

func kalkulackaSVJ(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Origin") != "https://"+r.Host {
		http.Error(w, "Cizí původ požadavku.", http.StatusForbidden)
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, 2048)
	if err := r.ParseForm(); err != nil {
		http.Error(w, "Chybný formulář.", http.StatusBadRequest)
		return
	}
	d, ok := spocitejSVJ(r)
	if !ok {
		http.Error(w, "Zkontrolujte výběr, spotřebu, cenu a procento úspory.", http.StatusUnprocessableEntity)
		return
	}
	if r.URL.Path == "/web-test/kalkulacka-svj/" {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		svjVysledek.Execute(w, d)
		return
	}
	select {
	case svjTisk <- struct{}{}:
		defer func() { <-svjTisk }()
	default:
		w.Header().Set("Retry-After", "3")
		http.Error(w, "Probíhá tisk podkladu. Zopakujte stažení.", http.StatusServiceUnavailable)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	data, _ := json.Marshal(d)
	cmd := exec.CommandContext(ctx, "/usr/local/bin/polarita-typst", "compile", "--root", ".", "--ignore-system-fonts", "--input", "model="+string(data), "-", "-")
	cmd.Dir = "/usr/local/share/polarita-web"
	cmd.Stdin = strings.NewReader(svjTypst)
	pdf, err := cmd.Output()
	if err != nil || !bytes.HasPrefix(pdf, []byte("%PDF-")) {
		http.Error(w, "Sazbu PDF se nepodařilo dokončit.", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", `attachment; filename="podklad-svj-test.pdf"`)
	w.Write(pdf)
}
