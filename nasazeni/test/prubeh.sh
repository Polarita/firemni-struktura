#!/bin/bash
# Sdílený řadič pro skutečné nasazení i zkoušku přerušeného běhu.
proved_kroky() {
    local posledni krok
    local konec="${!#}"
    posledni=$("${guest[@]}" sh -ec 'if test -f "$1"; then cat "$1"; else echo null; fi' -- "$stav/prubeh.json" |
        python3 "$prubeh" obnov "$tmp" "$cil" "$@")
    if [[ -n $posledni ]]; then
        if over_vstup; then
            printf 'Návaznost ověřena po kroku %s.\n' "$posledni"
        elif [[ $? == 74 ]]; then
            printf 'Kontrola přihlášení vypršela. Zachovávám průběh po kroku %s.\n' "$posledni" >&2
            return 74
        else
            printf 'Vstup po přerušení vyžaduje opravu, začínám od portálu.\n'
            posledni=
            rm -f -- "$tmp"/*.txt
        fi
    fi
    if [[ -z $posledni ]]; then "${guest[@]}" rm -f -- "$stav/prubeh.json"; fi
    for krok in "$@"; do
        if [[ -n $posledni ]]; then
            if [[ $krok == "$posledni" ]]; then posledni=; fi
            continue
        fi
        printf 'Instalace TEST – %s\n' "$krok"
        "$krok"
        if [[ $krok != "$konec" ]]; then
            python3 "$prubeh" zabal "$tmp" "$cil" "$krok" |
                "${guest[@]}" python3 "$dest/$prubeh" uloz "$stav/prubeh.json"
        fi
    done
    "${guest[@]}" rm -f -- "$stav/prubeh.json"
}
