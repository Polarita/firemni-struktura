variable "image" {
  type = string
}
resource "incus_instance" "umami" {
  name     = "umami-test"
  image    = "local:${var.image}"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"      = "true"
    "security.privileged" = "false"
    "limits.memory"       = "448MiB"
    "oci.entrypoint"      = "/bin/sh /etc/polarita-umami/start.sh"
    "oci.cwd"             = "/app"
    "user.polarita.role"  = "umami-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.22"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/umami-test/conf"
      path     = "/etc/polarita-umami"
      readonly = "true"
    }
  }
  device {
    name = "runtime"
    type = "disk"
    properties = {
      source         = "tmpfs:"
      path           = "/run"
      size           = "16MiB"
      "initial.mode" = "0755"
    }
  }
}
