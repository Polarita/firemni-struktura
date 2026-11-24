ui = false
disable_mlock = true
disable_cache = true
api_addr = "https://10.239.33.10:8200"
cluster_addr = "https://10.239.33.10:8201"

storage "raft" {
  path = "/var/lib/polarita-openbao/raft"
  node_id = "polarita-hq-test"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  cluster_address = "10.239.33.10:8201"
  tls_cert_file = "/var/lib/polarita-openbao/tls/server.crt"
  tls_key_file = "/var/lib/polarita-openbao/tls/server.key"
  tls_min_version = "tls12"
}

seal "static" {
  current_key_id = "polarita-test-01"
  current_key = "file:///run/openbao-seal/klíč"
}

audit "file" "audit-test" {
  description = "Audit zkušebního trezoru Polarity"
  options {
    file_path = "/var/lib/polarita-openbao/audit/pristupy.jsonl"
    mode = "0600"
    log_raw = "false"
  }
}
