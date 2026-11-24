locals {
  # Relativní k adrese uvedené v předinstalační inventuře.
  networks = {
    dmz_edge     = "10.239.31.1/24"
    app_internal = "10.239.32.1/24"
    data_vault   = "10.239.33.1/24"
  }
}
resource "incus_network" "zone" {
  for_each = local.networks
  name     = each.key
  type     = "bridge"
  config = merge({
    "ipv4.address"  = each.value
    "ipv4.nat"      = "false"
    "ipv4.firewall" = "false"
    "ipv6.address"  = "none"
    "dns.mode"      = "none"
    }, each.key == "dmz_edge" ? {
    "raw.dnsmasq" = <<-DNS
      no-resolv
      no-hosts
      local=/polarita.test/
      host-record=vpn.polarita.test,10.239.31.10
      host-record=stun.polarita.test,10.239.31.11
      dhcp-option=option:dns-server,10.239.31.1
    DNS
  } : {})
}
resource "incus_profile" "zone" {
  for_each = toset(concat(keys(local.networks), ["sandbox_airgap"]))
  name     = each.key
  config = {
    "limits.cpu"       = "1"
    "limits.memory"    = "192MiB"
    "limits.processes" = "192"
  }
  device {
    name       = "eth0"
    type       = each.key == "sandbox_airgap" ? "none" : "nic"
    properties = each.key == "sandbox_airgap" ? {} : { network = incus_network.zone[each.key].name }
  }
}
