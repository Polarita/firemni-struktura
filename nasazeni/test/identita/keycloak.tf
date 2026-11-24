variable "identity_url" {
  type = string
}

resource "incus_instance" "identita" {
  name     = "keycloak-test"
  image    = "local:e26c9eb621347b93b0d5e894df7c37f8d7710067628823cf917cf161cbe04769"
  profiles = ["default", "app_internal"]
  config = {
    "boot.autostart"                         = "true"
    "limits.memory"                          = "640MiB"
    "limits.memory.swap"                     = "false"
    "oci.entrypoint"                         = "/bin/bash /etc/polarita-id/start.sh"
    "user.polarita.role"                     = "keycloak-test"
    "environment.KC_HOSTNAME"                = var.identity_url
    "environment.KC_HTTP_RELATIVE_PATH"      = "/identita"
    "environment.KC_HTTP_ENABLED"            = "true"
    "environment.KC_PROXY_HEADERS"           = "xforwarded"
    "environment.KC_PROXY_TRUSTED_ADDRESSES" = "10.239.31.10"
    "environment.KC_DB"                      = "postgres"
    "environment.KC_DB_URL"                  = "jdbc:postgresql://10.239.33.12:5432/keycloak?sslmode=verify-full&sslrootcert=/etc/polarita-id/ca.crt"
    "environment.KC_DB_USERNAME"             = "keycloak"
    "environment.KC_DB_POOL_INITIAL_SIZE"    = "1"
    "environment.KC_DB_POOL_MIN_SIZE"        = "1"
    "environment.KC_DB_POOL_MAX_SIZE"        = "6"
    "environment.KC_CACHE"                   = "local"
    "environment.JAVA_OPTS_KC_HEAP"          = "-Xms64m -Xmx320m -XX:MaxMetaspaceSize=176m"
    "environment.JAVA_OPTS_APPEND"           = "-XX:ActiveProcessorCount=2 -XX:+ExitOnOutOfMemoryError"
  }
  device {
    name = "eth0"
    type = "nic"
    properties = {
      network                   = "app_internal"
      "ipv4.address"            = "10.239.32.11"
      "security.ipv4_filtering" = "true"
      "security.ipv6_filtering" = "true"
      "security.mac_filtering"  = "true"
    }
  }
  device {
    name = "konfigurace"
    type = "disk"
    properties = {
      source   = "/srv/polarita/infra/keycloak-test/conf"
      path     = "/etc/polarita-id"
      readonly = "true"
    }
  }
  device {
    name = "realm"
    type = "disk"
    properties = {
      source   = "/srv/polarita/vault/keycloak-test/import"
      path     = "/opt/keycloak/data/import"
      readonly = "true"
      shift    = "true"
    }
  }
}
