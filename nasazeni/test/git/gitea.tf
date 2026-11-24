resource "incus_instance" "gitea" {
  name     = "gitea-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "256MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "gitea-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.13"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "binarni"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/gitea-test/bin"
      path     = "/opt/gitea"
      readonly = "true"
    }
  }
  device {
    name = "repozitare"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/gitea/test"
      path   = "/var/lib/gitea"
      shift  = "true"
    }
  }
}
