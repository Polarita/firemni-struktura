variable "obraz" {
  type = string
}

resource "incus_instance" "akademie" {
  name     = "akademie-test"
  image    = "local:${var.obraz}"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"      = "true"
    "security.privileged" = "false"
    "limits.memory"       = "384MiB"
    "user.polarita.role"  = "akademie-test"
  }
  lifecycle {
    prevent_destroy = true
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.24"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "aplikace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/apps/akademie-test"
      path     = "/opt/polarita-akademie"
      readonly = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/akademie-test/moodledata"
      path   = "/var/lib/polarita-akademie"
      shift  = "true"
    }
  }
}
