resource "incus_instance" "zaloha" {
  name     = "restic-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "data_vault"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "160MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "restic-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "data_vault"
      "ipv4.address"            = "10.239.33.15"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "repozitar"
    type = "disk"
    properties = {
      source = "/srv/polarita/backups/restic-test"
      path   = "/var/lib/restic-test"
      shift  = "true"
    }
  }
}
