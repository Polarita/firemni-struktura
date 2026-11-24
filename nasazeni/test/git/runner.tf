resource "incus_instance" "runner" {
  name     = "gitea-runner-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"     = "false"
    "limits.cpu"         = "1"
    "limits.memory"      = "512MiB"
    "limits.memory.swap" = "false"
    "user.polarita.role" = "gitea-runner-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      host_name                 = "polrunner0"
      "ipv4.address"            = "10.239.32.14"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "wheels"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/gitea-runner-test/podklady/wheels"
      path     = "/opt/polarita-wheels"
      readonly = "true"
    }
  }
  device {
    name = "prohlizec"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/gitea-runner-test/podklady/prohlizec"
      path     = "/opt/polarita-prohlizec"
      readonly = "true"
    }
  }
  device {
    name = "aigis"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/gitea-runner-test/podklady/aigis"
      path     = "/opt/polarita-aigis"
      readonly = "true"
    }
  }
}
