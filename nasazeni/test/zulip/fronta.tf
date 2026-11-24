resource "incus_instance" "fronta" {
  name     = "zulip-fronta-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "448MiB"
    "user.polarita.role" = "zulip-fronta-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      host_name                 = "polzfront0"
      "ipv4.address"            = "10.239.32.17"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/zulip/fronta"
      path   = "/var/lib/rabbitmq"
      shift  = "true"
    }
  }
}
