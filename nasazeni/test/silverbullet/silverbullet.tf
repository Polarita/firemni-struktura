resource "incus_instance" "silverbullet" {
  name     = "silverbullet-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"      = "true"
    "limits.memory"       = "256MiB"
    "security.privileged" = "false"
    "user.polarita.role"  = "silverbullet-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.19"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "binarni"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/silverbullet-test/bin"
      path     = "/opt/polarita-silverbullet"
      readonly = "true"
    }
  }
  device {
    name = "cteni"
    type = "disk"
    properties = {
      source   = "/srv/polarita/data/silverbullet-test/overene"
      path     = "/var/lib/polarita-znalosti"
      readonly = "true"
    }
  }
}
