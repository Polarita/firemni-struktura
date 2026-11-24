resource "incus_instance" "pecet" {
  name     = "pecet-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "192MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "pecet-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.12"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "balicky"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/pecet-test/wheels"
      path     = "/opt/pecet-wheels"
      readonly = "true"
    }
  }
}
