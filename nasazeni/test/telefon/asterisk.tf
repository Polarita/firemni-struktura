resource "incus_instance" "asterisk" {
  name     = "asterisk-test"
  image    = "local:0feacf077c306d8c1fe37b18ee14154d21100fa39ddc99bf8b48dd6c43141a50"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"       = "false"
    "security.privileged"  = "false"
    "limits.cpu"           = "1"
    "limits.cpu.priority"  = "0"
    "limits.disk.priority" = "0"
    "limits.memory"        = "256MiB"
    "user.polarita.role"   = "asterisk-test"
  }
  device {
    name       = "eth0"
    type       = "none"
    properties = {}
  }
}
