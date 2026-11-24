resource "incus_instance" "signatury" {
  name     = "clamav-signatury-test"
  image    = "local:polarita-clamav-db-1.5.4"
  profiles = ["default", "dmz_edge"]
  config = {
    "boot.autostart"     = "true"
    "limits.memory"      = "448MiB"
    "limits.memory.swap" = "false"
    "oci.entrypoint"     = "/bin/sh -c 'exec sleep infinity'"
    "user.polarita.role" = "clamav-signatury-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "dmz_edge"
      "ipv4.address"            = "10.239.31.13"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "distribuce"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/clamav-db/test"
      path   = "/data/polarita-db"
      shift  = "true"
    }
  }
}
