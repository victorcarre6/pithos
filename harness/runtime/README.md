# Runtime Docker

La baseline autonome exécute Pi dans une image sans home hôte, sans Docker socket et sans variables de secrets.
Le workspace et les artefacts restent sur l'hôte. Le réseau `pithos-agent` est interne ; seul Squid possède une
sortie externe et applique l'allowlist de `egress/squid.conf`.

```bash
docker build -t pithos-agent:local harness/runtime/agent
PITHOS_LOGS_ROOT="$HOME/logs/pithos" docker compose -f harness/runtime/docker-compose.yml up -d
```

Le runner Docker utilise `harness/config/pi-docker/`, dont l'URL Ollama cible `host.docker.internal`. La configuration
source est montée read-only puis copiée dans un tmpfs privé pour permettre les fichiers runtime de Pi sans
altérer la source contrôlée par l'utilisateur.

Chaque run utilise `http://<run_id>@pithos-egress:3128` comme proxy. Le username non secret permet d'attribuer
les lignes de `~/logs/pithos/network/access.log` au run. Toute modification d'allowlist est une modification
versionnée du harness ; aucun domaine libre n'est accepté par défaut.
