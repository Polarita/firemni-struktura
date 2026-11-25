resource "incus_instance" "medusa" {
  name     = "medusa-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"      = "true"
    "security.privileged" = "false"
    "limits.memory"       = "896MiB"
    "user.polarita.role"  = "medusa-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.23"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "node"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/medusa-test/distribuce/node-v26.13.1-linux-x64"
      path     = "/opt/node"
      readonly = "true"
    }
  }
  device {
    name = "vstup-dmz"
    type = "proxy"
    properties = {
      listen  = "tcp:10.239.31.1:18450"
      connect = "tcp:127.0.0.1:9000"
    }
  }
  device {
    name = "software"
    type = "disk"
    properties = {
      source   = "/srv/polarita/apps/medusa-test"
      path     = "/opt/medusa"
      readonly = "true"
    }
  }
}
