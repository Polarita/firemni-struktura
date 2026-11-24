resource "incus_instance" "valkey" {
  name     = "valkey-test"
  image    = var.valkey_image
  profiles = ["default", "data_vault"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "144MiB"
    "limits.memory.swap" = "false"
    "oci.entrypoint"     = "/bin/sh /etc/polarita-valkey/start.sh"
    "user.polarita.role" = "valkey-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "data_vault"
      "ipv4.address"            = "10.239.33.13"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/valkey-test/conf"
      path     = "/etc/polarita-valkey"
      readonly = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      pool   = data.incus_storage_pool.default.name
      source = incus_storage_volume.valkey.name
      path   = "/data"
    }
  }
}
variable "valkey_image" {
  type = string
}
resource "incus_storage_volume" "valkey" {
  name = "valkey-test-data"
  pool = data.incus_storage_pool.default.name
  type = "custom"
  config = {
    size = "256MiB"
  }
}
