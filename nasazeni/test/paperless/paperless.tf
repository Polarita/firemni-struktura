variable "image" {
  type = string
}
variable "broker_image" {
  type = string
}

resource "incus_instance" "archiv" {
  name     = "paperless-test"
  image    = "local:${var.image}"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"      = "true"
    "limits.memory"       = "768MiB"
    "user.polarita.role"  = "paperless-test"
    "oci.entrypoint"      = "/bin/bash /etc/polarita-paperless/start.sh"
    "security.privileged" = "false"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.21"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/paperless-test/conf"
      path     = "/etc/polarita-paperless"
      readonly = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/paperless-test/aplikace"
      path   = "/var/lib/polarita-paperless"
      shift  = "true"
    }
  }
  device {
    name = "ocr"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/paperless-test/zdroje/ces.traineddata"
      path     = "/usr/share/tesseract-ocr/5/tessdata/ces.traineddata"
      readonly = "true"
    }
  }
  device {
    name = "socket"
    type = "disk"
    properties = {
      source   = "/srv/polarita/data/paperless-test/socket"
      path     = "/run/paperless-broker"
      shift    = "true"
      readonly = "true"
    }
  }
}

resource "incus_instance" "fronta" {
  name     = "paperless-fronta-test"
  image    = "local:${var.broker_image}"
  profiles = ["default"]
  config = {
    "boot.autostart"      = "true"
    "limits.memory"       = "96MiB"
    "security.privileged" = "false"
    "user.polarita.role"  = "paperless-fronta-test"
    "oci.entrypoint"      = "/bin/sh /etc/polarita-paperless/broker.sh"
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/paperless-test/conf/broker.sh"
      path     = "/etc/polarita-paperless/broker.sh"
      readonly = "true"
    }
  }
  device {
    name = "data"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/paperless-test/fronta"
      path   = "/data"
      shift  = "true"
    }
  }
  device {
    name = "socket"
    type = "disk"
    properties = {
      source = "/srv/polarita/data/paperless-test/socket"
      path   = "/run/paperless-broker"
      shift  = "true"
    }
  }
}
