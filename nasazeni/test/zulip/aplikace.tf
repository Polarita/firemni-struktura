variable "image" {
  type = string
}
variable "fqdn" {
  type = string
}

resource "incus_instance" "chat" {
  name     = "zulip-test"
  image    = "local:${var.image}"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"           = "true"
    "limits.memory"            = "2GiB"
    "user.polarita.role"       = "zulip-test"
    "oci.entrypoint"           = "/bin/bash /etc/polarita-zulip/start.sh"
    "environment.POLARITA_WEB" = var.fqdn
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.16"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/zulip-test/conf"
      path     = "/etc/polarita-zulip"
      readonly = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/zulip/aplikace"
      path   = "/data"
      shift  = "true"
    }
  }
}
