#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
ds=polarita_zfs/data/legal-archive/test
dir=/srv/polarita/data/legal-archive/test
[[ $(zfs get -Ho value mountpoint "$ds") == "$dir" ]]
[[ $(zfs get -Ho value keystatus "$ds") == available ]]
if [[ $(zfs get -Ho value mounted "$ds") != yes ]]; then zfs mount "$ds"; fi
[[ $(findmnt -n -o SOURCE --mountpoint "$dir") == "$ds" ]]
