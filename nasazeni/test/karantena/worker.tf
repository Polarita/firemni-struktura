resource "incus_instance" "karantena" {
  name     = "karantena-test"
  image    = "local:22655b2c907cb79bded8c9a6fc3fbc7cc1a15a241da01c5c63206084dd19a412"
  type     = "virtual-machine"
  profiles = ["default", "sandbox_airgap"]
  running  = false
  config = {
    "boot.autostart"      = "false"
    "limits.memory"       = "1152MiB"
    "limits.cpu"          = "1"
    "security.secureboot" = "false"
    "user.polarita.role"  = "karantena-test"
  }
  device {
    name = "vstup"
    type = "disk"
    properties = {
      source   = "/srv/polarita/data/airgap-spool/test/in"
      path     = "/mnt/karantena-in"
      readonly = "true"
    }
  }
  device {
    name = "vystup"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/airgap-spool/test/out"
      path   = "/mnt/karantena-out"
    }
  }
  device {
    name = "signatury"
    type = "disk"
    properties = {
      source   = "/srv/polarita/data/clamav-db/test"
      path     = "/mnt/clamav-db"
      readonly = "true"
    }
  }
  device {
    name = "root"
    type = "disk"
    properties = {
      path = "/"
      pool = data.incus_storage_pool.default.name
      size = "12GiB"
    }
  }
}
