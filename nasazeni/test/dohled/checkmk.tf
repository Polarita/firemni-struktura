resource "incus_instance" "dohled" {
  name     = "checkmk-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "768MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "checkmk-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.15"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "dohled"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/checkmk/test"
      path   = "/omd/sites"
      shift  = "true"
    }
  }
}
