package main

import (
	"crypto/sha256"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// A client sending its login form slowly must not block another device's login page.
type slowForm struct {
	reading chan struct{}
	release chan struct{}
}

func (body *slowForm) Read([]byte) (int, error) {
	close(body.reading)
	<-body.release
	return 0, io.EOF
}

func TestSimultaneousLoginPage(t *testing.T) {
	p := &portal{sessions: make(map[string]time.Time)}
	body := &slowForm{make(chan struct{}), make(chan struct{})}
	slow := httptest.NewRequest(http.MethodPost, "/prihlasit", body)
	slow.RemoteAddr = "127.0.0.1:4000"
	slow.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	done := make(chan struct{})
	go func() {
		p.ServeHTTP(httptest.NewRecorder(), slow)
		close(done)
	}()
	defer func() { close(body.release); <-done }()
	select {
	case <-body.reading:
	case <-time.After(3 * time.Second):
		t.Fatal("Login handler did not start reading")
	}
	second := httptest.NewRequest(http.MethodGet, "/", nil)
	second.RemoteAddr = "127.0.0.1:4001"
	resp := httptest.NewRecorder()
	ready := make(chan struct{})
	go func() { p.ServeHTTP(resp, second); close(ready) }()
	select {
	case <-ready:
		if resp.Code != 200 || !strings.Contains(resp.Body.String(), "Přihlášení do testovacího prostředí") {
			t.Fatal("Expected login page")
		}
	case <-time.After(3 * time.Second):
		t.Fatal("One client blocked the other")
	}
}

func TestLoginRotationAndLimit(t *testing.T) {
	digest := sha256.Sum256([]byte("synthetic"))
	p := &portal{digest: digest, sessions: make(map[string]time.Time)}
	token, status := p.login("spravce", "synthetic", "")
	if token == "" || status != http.StatusOK {
		t.Fatal("First login failed")
	}
	next, status := p.login("spravce", "synthetic", token)
	if next == token || status != http.StatusOK || !p.sessions[token].IsZero() {
		t.Fatal("Session rotation failed")
	}
	for i := 0; i < 10; i++ {
		if _, status := p.login("spravce", "", ""); status != http.StatusUnauthorized {
			t.Fatal("Unexpected rejection status")
		}
	}
	if _, status := p.login("spravce", "synthetic", ""); status != http.StatusTooManyRequests {
		t.Fatal("Expected rate limit")
	}
}
