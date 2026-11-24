resource "incus_storage_volume" "trezor" {
  pool = data.incus_storage_pool.default.name
  name = "openbao-test-raft"
  type = "custom"
  lifecycle {
    prevent_destroy = true
  }
}

resource "incus_instance" "trezor" {
  name     = "openbao-test"
  image    = "local:polarita-openbao-test-2.7.3"
  profiles = ["default", "data_vault"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "448MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "trezor-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "data_vault"
      "ipv4.address"            = "10.239.33.10"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "raft"
    type = "disk"
    properties = {
      pool   = data.incus_storage_pool.default.name
      source = incus_storage_volume.trezor.name
      path   = "/var/lib/polarita-openbao"
    }
  }
}
