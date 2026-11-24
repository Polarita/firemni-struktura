# Sdílená kontrola přesných parametrů místních spojení mezi službami.
device() {
    local instance=$1 name=$2 pair key
    shift 2
    [[ $(incus config get "$instance" user.polarita.role) == "$instance" ]]
    if ! incus config device list "$instance" | grep -Fxq "$name"; then
        incus config device add "$instance" "$name" proxy "$@"
    fi
    for pair in "$@"; do
        key=${pair%%=*}
        [[ $(incus config device get "$instance" "$name" "$key") == "${pair#*=}" ]]
    done
}
