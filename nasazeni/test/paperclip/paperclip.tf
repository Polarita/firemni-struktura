resource "incus_instance" "paperclip" {
  name     = "paperclip-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "768MiB"
    "user.polarita.role" = "paperclip-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      host_name                 = "polpaper0"
      "ipv4.address"            = "10.239.32.18"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/paperclip/test"
      path   = "/var/lib/paperclip"
      shift  = "true"
    }
  }
  device {
    name = "node"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/paperclip-test/distribuce/node-v24.22.3-linux-x64"
      path     = "/opt/node"
      readonly = "true"
    }
  }
}
