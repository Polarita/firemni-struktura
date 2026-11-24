resource "incus_instance" "hesla" {
  name     = "vaultwarden-test"
  image    = "local:polarita-vaultwarden-test-1.37.5"
  profiles = ["default", "data_vault"]
  config = {
    "boot.autostart"                    = "true"
    "limits.memory"                     = "256MiB"
    "limits.memory.swap"                = "false"
    "user.polarita.role"                = "vaultwarden-test"
    "environment.DOMAIN"                = var.vaultwarden_url
    "environment.ROCKET_ADDRESS"        = "0.0.0.0"
    "environment.ROCKET_PORT"           = "8080"
    "environment.SIGNUPS_ALLOWED"       = "false"
    "environment.INVITATIONS_ALLOWED"   = "false"
    "environment.SHOW_PASSWORD_HINT"    = "false"
    "environment.DISABLE_ICON_DOWNLOAD" = "true"
    "environment.LOG_LEVEL"             = "warn"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "data_vault"
      "ipv4.address"            = "10.239.33.11"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "hesla"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/vaultwarden/test"
      shift  = "true"
      path   = "/data"
    }
  }
}

variable "vaultwarden_url" {
  type = string
}
