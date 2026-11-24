resource "incus_storage_volume" "mx" {
  name = "stalwart-mx-test-data"
  pool = data.incus_storage_pool.default.name
  type = "custom"
  lifecycle {
    prevent_destroy = true
  }
}

resource "incus_instance" "mx" {
  name     = "stalwart-mx-test"
  image    = "ghcr:stalwartlabs/stalwart@sha256:79ea09d25baad7e074d8df53db474571c5dc62621298e35e09e9cfd764333ed8"
  profiles = ["default", "dmz_edge"]
  config = {
    "boot.autostart"     = "true"
    "oci.entrypoint"     = "/bin/sh /etc/polarita-mx/start.sh"
    "limits.memory"      = "448MiB"
    "user.polarita.role" = "testovaci-mx"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "dmz_edge"
      "ipv4.address"            = "10.239.31.12"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/mx-test/conf"
      path     = "/etc/polarita-mx"
      readonly = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      pool   = data.incus_storage_pool.default.name
      source = incus_storage_volume.mx.name
      path   = "/var/lib/stalwart"
    }
  }
}
