#!/bin/bash
# Installe ou met à jour litsearch et crée le lanceur « Recherche biblio » sur le Bureau.
# Double-cliquez sur ce fichier (la première fois : clic droit > Ouvrir). Relancez-le pour mettre à jour.
set -e

# Adresse de l'archive du dépôt (à renseigner une fois par le mainteneur) :
REPO_ZIP="https://github.com/TaoHuaLiu/litsearch/archive/refs/heads/main.zip"

export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
    echo "Installation de uv, le gestionnaire Python..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "Téléchargement et installation de litsearch..."
uv tool install --python 3.12 --force --reinstall --refresh "litsearch[gui] @ $REPO_ZIP"
uv tool update-shell >/dev/null 2>&1 || true

launcher="$HOME/Desktop/Recherche biblio.command"
printf '#!/bin/bash\nexec "%s/.local/bin/litsearch-gui"\n' "$HOME" > "$launcher"
chmod +x "$launcher"
echo
echo "Terminé. Double-cliquez sur « Recherche biblio » sur le Bureau : la page s'ouvre dans votre navigateur."
echo "Gardez la fenêtre du Terminal ouverte tant que vous utilisez l'outil."
