terraform {
  required_providers {
    incus = {
      source = "lxc/incus"
    }
  }
}

provider "incus" {
  default_remote = "local"

  remote {
    name    = "local"
    address = "unix://"
  }
}

data "incus_storage_pool" "default" {
  name = "default"

  lifecycle {
    postcondition {
      condition     = self.driver == "zfs" && self.config["source"] == "polarita_zfs/data/incus/pool"
      error_message = "Vnitřní Incus musí používat vyhrazený dataset ZFS."
    }
  }
}
