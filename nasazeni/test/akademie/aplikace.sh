#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
app=/srv/polarita/apps/akademie-test
distrib=/srv/polarita/infra/akademie-test/distribuce
inside=(incus exec -T akademie-test --)
exec 9>/run/polarita-akademie-aplikace.lock
flock 9
exec 8>/run/polarita-test-zatez.lock
flock 8
rev=$(cd "$src" && sha256sum distribuce.lock.json knihovny.lock.json knihovny.py rozbal.py aplikace.sh polaritavalkey/*.php polaritavalkey/db/*.php polaritavalkey/classes/task/*.php polaritavalkey/lang/*/*.php | sha256sum | cut -d' ' -f1)
install -dm0755 "$app/releases"
release=$app/releases/$rev
if [[ ! -d $release ]]; then
    tmp=$(mktemp -d "$app/.sestaveni-XXXXXXXX")
    stage=
    cleanup() {
        rm -rf -- "$tmp"
        if [[ -n $stage ]]; then "${inside[@]}" rm -rf -- "$stage"; fi
    }
    trap cleanup EXIT
    python3 "$src/podklady.py"
    tar --no-same-owner --no-same-permissions -xzf "$distrib/moodle-5.3.1.tgz" --strip-components=1 -C "$tmp"
    python3 "$src/rozbal.py" "$tmp"
    cp -R "$src/polaritavalkey" "$tmp/public/cache/stores/"
    chmod -R a+rX "$tmp/public/cache/stores/polaritavalkey"
    stage=$("${inside[@]}" mktemp -d /var/tmp/polarita-composer-XXXXXXXX)
    [[ $stage == /var/tmp/polarita-composer-* ]]
    "${inside[@]}" chown nobody:nogroup "$stage"
    python3 "$src/knihovny.py" "$tmp/composer.lock" "$tmp/.composer-local.lock"
    incus file push --mode=0644 "$tmp/.composer-local.lock" "akademie-test$stage/composer.lock"
    incus file push --mode=0644 "$tmp/composer.json" "akademie-test$stage/composer.json"
    rm -- "$tmp/.composer-local.lock"
    # ZIPy se zpřístupní jen tomuto procesu. Zdrojový strom v /opt je pro aplikaci pouze ke čtení.
    "${inside[@]}" install -dm0755 /opt/polarita-composer
    "${inside[@]}" install -dm0755 "$stage/balicky"
    tar -C "$distrib/composer" -cf - --files-from=<(cd "$distrib/composer" && find . -maxdepth 1 -name '*.zip' -type f) |
        "${inside[@]}" tar -xf - -C "$stage/balicky"
    "${inside[@]}" systemd-run --wait --quiet --collect --pipe --service-type=exec \
        -p User=nobody -p Group=nogroup -p NoNewPrivileges=yes -p PrivateNetwork=yes \
        -p "WorkingDirectory=$stage" -p "BindReadOnlyPaths=$stage/balicky:/opt/polarita-composer" \
        -E HOME="$stage" -E COMPOSER_DISABLE_NETWORK=1 -E COMPOSER_ALLOW_SUPERUSER=0 \
        /usr/bin/composer install --no-interaction --no-plugins --no-scripts --no-dev --prefer-dist --no-progress
    "${inside[@]}" test -s "$stage/vendor/autoload.php"
    "${inside[@]}" tar -C "$stage" -cf - vendor |
        python3 -c 'import sys,tarfile; tarfile.open(fileobj=sys.stdin.buffer,mode="r|").extractall(sys.argv[1],filter="data")' "$tmp"
    [[ -s $tmp/vendor/autoload.php && -s $tmp/admin/cli/install.php && -s $tmp/public/index.php &&
       -s $tmp/public/mod/customcert/version.php && -s $tmp/public/mod/offlinequiz/version.php && -s $tmp/jazyk/cs/langconfig.php ]]
    chmod 0755 "$tmp"
    mv -T "$tmp" "$release"
fi
"${inside[@]}" php8.4 -r '
    require $argv[1]."/vendor/autoload.php";
    foreach (["Slim\\Factory\\AppFactory", "GuzzleHttp\\Client", "Psr\\Log\\LoggerInterface"] as $name) {
        if (!class_exists($name) && !interface_exists($name)) exit(1);
    }' "/opt/polarita-akademie/releases/$rev"
ln -sfn "releases/$rev" "$app/.candidate-next"
mv -Tf "$app/.candidate-next" "$app/candidate"
echo "Zdroj Moodle 5.3.1, oba moduly, čeština a provozní knihovny jsou připraveny pro instalační CLI."
