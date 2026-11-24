// Spouštěč OpenBao Agenta pro systémové i minimální OCI kontejnery.
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"syscall"
	"time"
)

const target = "/run/secrets"
const private = target + "/.polarita-agent"
const tmpfs = 0x01021994

type grant struct {
	Gitea     bool     `json:"gitea"`
	Garage    bool     `json:"garage"`
	Caches    []string `json:"caches"`
	Seal      bool     `json:"seal"`
	Databases []string `json:"databases"`
	RoleID    string   `json:"role_id"`
	SecretID  string   `json:"secret_id"`
	Path      string   `json:"path"`
	UID       int      `json:"uid"`
	GID       int      `json:"gid"`
}

func memoryDirectory() error {
	if err := os.MkdirAll(target, 0755); err != nil {
		return err
	}
	resolved, err := filepath.EvalSymlinks(target)
	if err != nil || resolved != target {
		return fmt.Errorf("neočekávaná cesta k paměťovému médiu")
	}
	var fs syscall.Statfs_t
	if err := syscall.Statfs(target, &fs); err != nil {
		return err
	}
	if fs.Type != tmpfs {
		files, err := os.ReadDir(target)
		if err != nil || len(files) != 0 {
			return fmt.Errorf("cílový adresář na disku musí být prázdný")
		}
		if err := syscall.Mount("tmpfs", target, "tmpfs", syscall.MS_NOSUID|syscall.MS_NODEV|syscall.MS_NOEXEC, "mode=0755,size=1m"); err != nil {
			return err
		}
	}
	return os.MkdirAll(private, 0700)
}

func deliver() error {
	var g grant
	if err := json.NewDecoder(os.Stdin).Decode(&g); err != nil {
		return fmt.Errorf("neplatný dokument oprávnění")
	}
	if !regexp.MustCompile(`^[a-z0-9-]+$`).MatchString(g.Path) || g.RoleID == "" || g.SecretID == "" || g.UID < 0 || g.GID < 0 {
		return fmt.Errorf("neplatná role nebo příjemce")
	}
	if err := memoryDirectory(); err != nil {
		return err
	}
	lock, err := os.OpenFile(private+"/lock", os.O_RDWR|os.O_CREATE, 0600)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err := syscall.Flock(int(lock.Fd()), syscall.LOCK_EX); err != nil {
		return err
	}
	tmp, err := os.MkdirTemp(private, "behem-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmp)
	for filename, value := range map[string]string{"role": g.RoleID, "secret": g.SecretID} {
		if err := os.WriteFile(tmp+"/"+filename, []byte(value), 0400); err != nil {
			return err
		}
	}
	config := fmt.Sprintf(`exit_after_auth = true
vault {
  address = "https://10.239.33.10:8200"
  ca_cert = "/opt/polarita-openbao/ca.crt"
}
auto_auth {
  method "approle" {
    config = {
      role_id_file_path = "%s/role"
      secret_id_file_path = "%s/secret"
      remove_secret_id_file_after_reading = true
    }
  }
}
template_config {
  exit_on_retry_failure = true
}
template {
  destination = "%s/hodnota"
  perms = "0400"
  error_on_missing_key = true
  contents = "{{ with secret \"test/data/%s\" }}{{ .Data.data.vzorek }}{{ end }}"
}
`, tmp, tmp, tmp, g.Path)
	outputs := map[string]string{"hodnota": "polarita-test"}
	if g.Seal {
		config += fmt.Sprintf(`template {
  destination = "%s/pecet"
  perms = "0400"
  error_on_missing_key = true
  contents = "{{ with secret \"test/data/pki/organizace-test\" }}{{ .Data.data.sada }}{{ end }}"
}
`, tmp)
		outputs["pecet"] = "pecet-test"
	}
	if len(g.Caches) > 0 {
		acl := "user default off\n"
		for _, name := range g.Caches {
			if !regexp.MustCompile(`^[a-z]{1,20}$`).MatchString(name) {
				return fmt.Errorf("neplatné jméno klienta Valkey")
			}
			commands := "+ping +get +set +del +expire +ttl"
			if name == "zulip" {
				// Zulip uses transactions for login tokens and a Lua script for rate limits.
				commands += " +multi +exec +discard +evalsha +script|load +time +exists +pttl +hget +hset"
			}
			acl += fmt.Sprintf("user %s reset on #{{ with secret \"test/data/valkey-overeni/server\" }}{{ .Data.data.%s }}{{ end }} ~%s:* %s\n", name, name, name, commands)
		}
		config += fmt.Sprintf("template {\n destination = %q\n perms = \"0400\"\n error_on_missing_key = true\n contents = %q\n}\n", tmp+"/valkey-acl", acl)
		outputs["valkey-acl"] = "valkey-acl"
	}
	service := ""
	fields := []string{"cert", "klic"}
	if len(g.Caches) > 0 {
		service = "valkey"
	} else if g.Garage {
		service = "garage"
		fields = append(fields, "rpc", "admin")
	}
	if service != "" {
		for _, field := range fields {
			file := service + "-" + field
			template := fmt.Sprintf(`{{ with secret "test/data/pki/%s-test" }}{{ .Data.data.%s }}{{ end }}`, service, field)
			config += fmt.Sprintf("template {\n destination = %q\n perms = \"0400\"\n error_on_missing_key = true\n contents = %q\n}\n", tmp+"/"+file, template)
			outputs[file] = file
		}
	}
	if g.Gitea {
		template := `{{ with secret "test/data/pki/gitea-test" }}{{ .Data.data.sada }}{{ end }}`
		config += fmt.Sprintf("template {\n destination = %q\n perms = \"0400\"\n error_on_missing_key = true\n contents = %q\n}\n", tmp+"/gitea-stroj", template)
		outputs["gitea-stroj"] = "gitea-stroj"
	}
	for _, name := range g.Databases {
		if !regexp.MustCompile(`^[a-z][a-z0-9_]{0,40}$`).MatchString(name) {
			return fmt.Errorf("neplatný název databáze")
		}
		file := "pg-" + name
		config += fmt.Sprintf(`template {
  destination = "%s/%s"
  perms = "0400"
  error_on_missing_key = true
  contents = "{{ with secret \"test/data/databaze/%s\" }}{{ .Data.data.heslo }}{{ end }}"
}
`, tmp, file, name)
		outputs[file] = file
	}
	if err := os.WriteFile(tmp+"/agent.hcl", []byte(config), 0400); err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 85*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "/opt/polarita-openbao/bao", "agent", "-config="+tmp+"/agent.hcl", "-log-level=warn")
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("OpenBao Agent: %w", err)
	}
	for source, dest := range outputs {
		value, err := os.ReadFile(tmp + "/" + source)
		if err != nil || len(bytes.TrimSpace(value)) == 0 {
			return fmt.Errorf("agent nevrátil hodnotu do tmpfs")
		}
		if err := os.Chown(tmp+"/"+source, g.UID, g.GID); err != nil {
			return err
		}
		if err := os.Rename(tmp+"/"+source, target+"/"+dest); err != nil {
			return err
		}
	}
	return nil
}

func main() {
	if len(os.Args) == 2 && os.Args[1] == "--overit" {
		filename := target + "/polarita-test"
		var fs syscall.Statfs_t
		stat, err := os.Lstat(filename)
		if err != nil || !stat.Mode().IsRegular() || stat.Mode().Perm() != 0400 || syscall.Statfs(filename, &fs) != nil || fs.Type != tmpfs {
			fmt.Fprintln(os.Stderr, "Chybí chráněný soubor v tmpfs")
			os.Exit(1)
		}
		value, err := os.ReadFile(filename)
		if err != nil || len(value) == 0 {
			os.Exit(1)
		}
		fmt.Printf("%x", sha256.Sum256(value))
		return
	}
	if err := deliver(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
