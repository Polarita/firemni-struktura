variable "postgres_image" {
  type = string
}

resource "incus_instance" "postgres" {
  name     = "postgres-test"
  image    = var.postgres_image
  profiles = ["default", "data_vault"]
  lifecycle {
    prevent_destroy = true
    ignore_changes  = [image]
  }
  config = {
    "boot.autostart"     = "true"
    "limits.processes"   = "320"
    "limits.memory"      = "448MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "postgres-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "data_vault"
      "ipv4.address"            = "10.239.33.12"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "db"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/postgres/test"
      path   = "/var/lib/polarita-postgres"
      shift  = "true"
    }
  }
  device {
    name = "metadata-vystup"
    type = "proxy"
    properties = {
      bind    = "host"
      listen  = "unix:/srv/polarita/infra/metadata-test/api.sock"
      connect = "unix:/run/polarita-metadata-test/api.sock"
      mode    = "0600"
    }
  }
  device {
    name = "sanony-registr"
    type = "proxy"
    properties = {
      bind    = "host"
      listen  = "unix:/srv/polarita/infra/metadata-test/sanony.sock"
      connect = "unix:/run/polarita-sanony-registr.sock"
      mode    = "0600"
    }
  }
}
