resource "incus_instance" "vikunja" {
  name     = "vikunja-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"      = "true"
    "limits.memory"       = "256MiB"
    "security.privileged" = "false"
    "user.polarita.role"  = "vikunja-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.20"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "binarni"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/vikunja-test/bin"
      path     = "/opt/polarita-vikunja"
      readonly = "true"
    }
  }
  device {
    name = "soubory"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/vikunja-test"
      path   = "/var/lib/vikunja"
      shift  = "true"
    }
  }
}
