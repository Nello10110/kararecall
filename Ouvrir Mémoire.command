#!/bin/zsh
cd "${0:A:h}" || exit 1
printf '\nMémoire est accessible sur http://127.0.0.1:8765\nGardez cette fenêtre ouverte pour utiliser l’interface. Ctrl+C pour arrêter.\n\n'
/usr/bin/python3 web_server.py --host 127.0.0.1 --port 8765 --open-browser
