#!/bin/zsh
cd "${0:A:h}" || exit 1
while true; do
  printf '\nVotre souvenir (Entrée pour quitter) : '
  IFS= read -r souvenir
  [[ -z "$souvenir" ]] && break
  /usr/bin/python3 cerveau.py search --limit 3 -- "$souvenir"
done
