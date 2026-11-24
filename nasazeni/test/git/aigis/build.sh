#!/bin/bash
# Deterministické sestavení nástroje probíhá bez síťové karty, pod běžným účtem.
set -euo pipefail
[[ $(hostname -s) == aigis-build-test && $EUID == 0 ]]
[[ $(ls /sys/class/net) == lo ]]
base=/opt/polarita-aigis
rev=7b083bca7fde98f2b97bd93a658c28c24ef55317
install -d -m 0755 "$base/lib" "$base/include"
tar -xOf /opt/polarita-vstup/libkuzu.tar.gz libkuzu.so >"$base/lib/libkuzu.so"
tar -xOf /opt/polarita-vstup/libkuzu.tar.gz kuzu.hpp >"$base/include/kuzu.hpp"
tar -xOf /opt/polarita-vstup/libkuzu.tar.gz kuzu.h >"$base/include/kuzu.h"
chmod 0644 "$base/lib/libkuzu.so" "$base/include/kuzu.hpp" "$base/include/kuzu.h"
if ! id pol-build >/dev/null 2>&1; then useradd --system --create-home --home-dir /var/lib/polarita-build --shell /usr/sbin/nologin pol-build; fi
runuser -u pol-build -- env HOME=/var/lib/polarita-build KUZU_LIBRARY_DIR="$base/lib" KUZU_INCLUDE_DIR="$base/include" KUZU_SHARED=1 \
    CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 CARGO_PROFILE_RELEASE_DEBUG=0 CARGO_PROFILE_RELEASE_OPT_LEVEL=1 CARGO_PROFILE_RELEASE_CODEGEN_UNITS=32 \
    CARGO_TARGET_DIR=/var/lib/polarita-build/target bash -seu -- "$rev" <<'BUILD'
umask 022
cd "$HOME"
if [[ ! -d aigiscode-$1 ]]; then tar -xf /opt/polarita-vstup/aigiscode.tar.gz; fi
cd "aigiscode-$1"
# Oficiální sdílená distribuce Kuzu dodává grafové jádro. Výchozí Rust features
# přidávají statické archivy volitelných rozšíření, které AigisCode nevolá.
tar -xOf /opt/polarita-vstup/aigiscode.tar.gz "aigiscode-$1/Cargo.toml" >Cargo.toml.pramen
echo 'c4fcfb277761be209d203ad5250cf0241b19e66d6e6fb0e9258a3ae7706675ee  Cargo.toml.pramen' | sha256sum --status -c -
sed 's/^kuzu = "0.11.3"$/kuzu = { version = "=0.11.3", default-features = false }/' Cargo.toml.pramen >Cargo.toml.next
grep -Fxq 'kuzu = { version = "=0.11.3", default-features = false }' Cargo.toml.next
if ! cmp -s Cargo.toml.next Cargo.toml; then mv -T Cargo.toml.next Cargo.toml; fi
cargo rustc --package aigiscore --release --frozen --offline --bin aigiscode \
    --config 'source.crates-io.replace-with="polarita"' --config 'source.polarita.local-registry="/opt/polarita-vstup/registry"' \
    -- -C 'link-arg=-Wl,-rpath,$ORIGIN/lib'
BUILD
install -m 0755 /var/lib/polarita-build/target/release/aigiscode "$base/aigiscode"
install -m 0644 "/var/lib/polarita-build/aigiscode-$rev/LICENSE" "$base/LICENSE-aigiscode"
"$base/aigiscode" --version
