#!/bin/sh
# V kontejneru s uzavřenou sítí pracuje pouze s ověřenými soubory v adresáři přípravy.
set -eu
stage=$1
trap 'rm -r -- "$stage"' EXIT
export DEBIAN_FRONTEND=noninteractive
apt-get -y --no-install-recommends -o DPkg::Lock::Timeout=1800 \
    -o "Dir::State::Lists=$stage/lists" -o Dir::Etc::sourcelist=/dev/null -o Dir::Etc::sourceparts=- install "$stage"/*.deb
