resource "incus_instance" "caddy" {
  name     = "caddy-test"
  image    = "docker:library/caddy@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0"
  profiles = ["default", "dmz_edge"]
  config = {
    "boot.autostart"     = "true"
    "user.polarita.role" = "caddy-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "dmz_edge"
      "ipv4.address"            = "10.239.31.10"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "caddyfile"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/hrana/conf"
      path     = "/etc/caddy"
      readonly = "true"
    }
  }
  device {
    name = "vstup"
    type = "proxy"
    properties = {
      listen  = "tcp:127.0.0.1:18184"
      connect = "tcp:127.0.0.1:8080"
    }
  }
}

resource "incus_storage_volume" "headscale" {
  name = "headscale-test-data"
  pool = "default"
  type = "custom"
  lifecycle {
    prevent_destroy = true
  }
}

resource "incus_instance" "headscale" {
  name     = "headscale-test"
  image    = "ghcr:juanfont/headscale@sha256:11f81665e842809db9fe3006a38c56a66e968baa5abd4bac498e86445572b970"
  profiles = ["default", "dmz_edge"]
  config = {
    "boot.autostart"     = "true"
    "oci.entrypoint"     = "/ko-app/headscale serve --config /etc/headscale/config.yaml"
    "user.polarita.role" = "headscale-test"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "dmz_edge"
      "ipv4.address"            = "10.239.31.11"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/hrana/headscale"
      path     = "/etc/headscale"
      readonly = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      pool   = "default"
      source = incus_storage_volume.headscale.name
      path   = "/var/lib/headscale"
    }
  }
}
