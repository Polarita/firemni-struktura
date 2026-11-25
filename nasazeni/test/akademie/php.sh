#!/bin/bash
# APT ve VM ověřuje podepsaný snímek Debianu vůči klíčům z obrazu kontejneru.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
target=akademie-test
inside=(incus exec -T "$target" --)
day=20261124T000000Z
work=/srv/polarita/infra/akademie-test/apt-$day
install -dm0755 "$work" "$work/lists/partial" "$work/archivy/partial"
exec 8>/run/polarita-test-zatez.lock
flock 8
cd "$work"
"${inside[@]}" sh -ec '. /etc/os-release; test "$ID:$VERSION_CODENAME" = debian:trixie'
incus file pull "$target/usr/share/keyrings/debian-archive-keyring.pgp" "$work/debian.gpg"
incus file pull "$target/var/lib/dpkg/status" "$work/status"
chmod 0644 debian.gpg
cat >debian.sources <<SOURCES
Types: deb
URIs: https://snapshot.debian.org/archive/debian/$day/
Suites: trixie
Components: main
Architectures: amd64
Signed-By: $work/debian.gpg
Check-Valid-Until: no

Types: deb
URIs: https://snapshot.debian.org/archive/debian-security/$day/
Suites: trixie-security
Components: main
Architectures: amd64
Signed-By: $work/debian.gpg
Check-Valid-Until: no
SOURCES
cat >apt.conf <<CONF
Dir::Etc::parts "-";
Dir::Etc::main "-";
Dir::Etc::sourcelist "$work/debian.sources";
Dir::Etc::sourceparts "-";
Dir::Etc::preferences "-";
Dir::Etc::preferencesparts "-";
Dir::State::status "$work/status";
Dir::State::lists "$work/lists";
Dir::Cache::archives "$work/archivy";
Dir::Cache::pkgcache "";
Dir::Cache::srcpkgcache "";
APT::Architecture "amd64";
Acquire::Languages "none";
Acquire::Retries "3";
CONF
export APT_CONFIG="$work/apt.conf"
apt-get update --error-on=any
sha256sum --check --status <<INDEXY
bfacad4ca61899ce20d4a0d439f29339f66541561b67506364efb88e27dee870  lists/snapshot.debian.org_archive_debian_${day}_dists_trixie_InRelease
8a396554cdf96a73116cb1212749ac1f440c209e379f55a52e5fe6af48a0e4db  lists/snapshot.debian.org_archive_debian-security_${day}_dists_trixie-security_InRelease
INDEXY
packages=(php8.4-fpm php8.4-cli php8.4-pgsql php8.4-xml php8.4-mbstring php8.4-curl
          php8.4-zip php8.4-gd php8.4-intl php8.4-soap php8.4-redis php8.4-opcache
          nginx-light composer unzip ca-certificates)
# Seznam URI zahrnuje jen balíčky, které podle stavu cíle ještě scházejí.
apt-get --download-only --no-install-recommends -y install "${packages[@]}"
unset APT_CONFIG
if ! "${inside[@]}" test -e /etc/nginx/sites-enabled/polarita-akademie; then
    "${inside[@]}" systemctl mask nginx.service php8.4-fpm.service
fi
# Po prvním běhu může APT ponechat archivy i pro další opakování. K přenosu vyber jen
# rozdílné verze podle skutečného stavu dpkg, aby se služby zbytečně nerestartovaly.
shopt -s nullglob
files=()
for file in "$work"/archivy/*.deb; do
    name=$(dpkg-deb -f "$file" Package)
    version=$(dpkg-deb -f "$file" Version)
    installed=$(dpkg-query --admindir="$work" -W -f='${db:Status-Status} ${Version}' "$name" 2>/dev/null || true)
    if [[ $installed != "installed $version" ]]; then files+=("${file##*/}"); fi
done
if ((${#files[@]})); then
    stage=$("${inside[@]}" mktemp -d /var/tmp/polarita-deb-XXXXXXXX)
    [[ $stage == /var/tmp/polarita-deb-* ]]
    trap '"${inside[@]}" rm -rf -- "$stage"' EXIT
    "${inside[@]}" install -dm0755 "$stage/lists/partial"
    tar -C "$work/archivy" -cf - -- "${files[@]}" | "${inside[@]}" tar -xf - -C "$stage"
    incus file push --mode=0755 "$src/../incus/instaluj-deb.sh" "$target$stage/instaluj-deb.sh"
    "${inside[@]}" sh "$stage/instaluj-deb.sh" "$stage"
fi
"${inside[@]}" sh -ec '
    for sapi in cli fpm; do
        conf=/etc/php/8.4/$sapi/conf.d/95-polarita-akademie.ini
        printf "max_input_vars = 5000\n" >"$conf.next"
        chmod 0644 "$conf.next"
        mv -T "$conf.next" "$conf"
    done
    php8.4 -r '\''if (PHP_MAJOR_VERSION !== 8 || PHP_MINOR_VERSION !== 4 || PHP_INT_SIZE !== 8 || (int)ini_get("max_input_vars") < 5000) exit(1);
    foreach (["sodium", "curl", "gd", "intl", "mbstring", "pgsql", "redis", "soap", "zip", "xmlreader"] as $module) {
        if (!extension_loaded($module)) { fwrite(STDERR, "Chybí PHP modul $module\n"); exit(1); }
    }
    echo "PHP ".PHP_VERSION." a rozšíření Akademie ověřeny.\n";'\''
    php-fpm8.4 -v | head -1
    composer --version --no-ansi
'
