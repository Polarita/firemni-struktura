resource "incus_instance" "garage" {
  name     = "garage-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "data_vault"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "224MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "garage-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "data_vault"
      "ipv4.address"            = "10.239.33.14"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "binarni"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/garage-test/bin"
      path     = "/opt/garage"
      readonly = "true"
    }
  }
  device {
    name = "objekty"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/garage/test"
      path   = "/var/lib/garage"
      shift  = "true"
    }
  }
}
