package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func TestKalkulackaSVJ(t *testing.T) {
	for _, c := range []struct {
		cena, kwh, procent, uspora, energie string
		valid                               bool
	}{
		{"5,50", "12000", "10", "6600", "1200", true}, {"4.99", "1", "10", "0", "0,1", true},
		{"0.50", "1", "100", "1", "1", true}, {"100", "10000000", "100", "1000000000", "10000000", true},
		{"1", "0", "0", "0", "0", true}, {"1e3", "12000", "10", "", "", false},
		{"-1", "12000", "10", "", "", false}, {"1.001", "12000", "10", "", "", false}, {"5", "12000", "101", "", "", false},
	} {
		form := url.Values{"subjekt": {"svj"}, "revize": {"nezjisteno"}, "cena": {c.cena}, "kwh": {c.kwh}, "procent": {c.procent}}
		r := &http.Request{PostForm: form}
		d, ok := spocitejSVJ(r)
		if ok != c.valid || ok && (d.Uspora != c.uspora || d.Energie != c.energie || strings.Contains(d.Riziko, "2 000 000")) {
			t.Fatalf("neočekávaný výsledek pro %v: %+v", form, d)
		}
	}
	form := url.Values{"subjekt": {"firma"}, "revize": {"po-lhute"}, "kwh": {"12000"}, "cena": {"5.50"}, "procent": {"10"}}
	for _, origin := range []string{"https://portal.test", "https://cizi.test"} {
		req := httptest.NewRequest("POST", "https://portal.test/web-test/kalkulacka-svj/", strings.NewReader(form.Encode()))
		req.Header.Set("Origin", origin)
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		res := httptest.NewRecorder()
		kalkulackaSVJ(res, req)
		if origin != "https://portal.test" {
			if res.Code != 403 {
				t.Fatal("chybí kontrola původu")
			}
			continue
		}
		if res.Code != 200 || !strings.Contains(res.Body.String(), "6600 Kč") || !strings.Contains(res.Body.String(), "2 000 000 Kč") || !strings.Contains(res.Body.String(), "podklad.pdf") {
			t.Fatal("neplatný výsledek formuláře")
		}
	}
	form.Add("cena", "1.00")
	if _, ok := spocitejSVJ(&http.Request{PostForm: form}); ok {
		t.Fatal("nejednoznačná cena")
	}
}
