"""SSH bootstrap + deploy do projeto no VPS via paramiko.

Roda comandos remotos com SSH key (preferido) ou password auth, captura
stdout/stderr/exit code.

Config via env vars:
  VPS_HOST   — hostname/IP do VPS         (default: soulfocus.io)
  VPS_USER   — usuario SSH                (default: root)
  VPS_KEY    — caminho da chave privada   (default: ~/.ssh/vps-hostinger-soul-focus)
  VPS_PASS   — password SSH               (fallback so se VPS_KEY nao existir)

Defaults apontam pro VPS Hostinger (soulfocus.io). Pra outro VPS:
  $env:VPS_HOST="x.x.x.x"; $env:VPS_USER="usr"; $env:VPS_PASS="..."
  python scripts/vps_deploy.py <action>

NOTA: o Hostinger ja roda nginx-proxy em Docker (auto-discovery via VIRTUAL_HOST
labels). A action `nginx` deste script instala nginx nativo do sistema e
conflita com nginx-proxy — usar apenas em VPS limpo (Contabo-style).
"""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

import paramiko

# Forca stdout UTF-8 pra acentos/unicode do apt nao quebrarem em Windows cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HOST = os.environ.get("VPS_HOST", "soulfocus.io")
USER = os.environ.get("VPS_USER", "root")
KEY_PATH = os.environ.get("VPS_KEY", str(Path.home() / ".ssh" / "vps-hostinger-soul-focus"))
PASS = os.environ.get("VPS_PASS")

# Auth: SSH key se o arquivo existir, senao password.
USE_KEY = Path(KEY_PATH).expanduser().is_file()

if not USE_KEY and not PASS:
    sys.exit(
        "ERROR: nenhum metodo de auth disponivel. Defina VPS_KEY apontando "
        "pra chave privada existente OU VPS_PASS com a senha."
    )

# Sudo: root nao precisa; outros usuarios precisam de password no -S.
NEEDS_SUDO_PW = USER != "root"
if NEEDS_SUDO_PW and not PASS:
    sys.exit("ERROR: actions com sudo precisam de VPS_PASS quando USER != root.")


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600, use_sudo_pw: bool = False) -> tuple[int, str, str]:
    """Run remote command. Returns (exit_code, stdout, stderr)."""
    print(f"\n>>> {cmd[:200]}")
    if use_sudo_pw and NEEDS_SUDO_PW:
        # Injeta password pra sudo via stdin (-S flag). Root pula isso.
        body = cmd[5:] if cmd.startswith("sudo ") else cmd
        cmd = f"echo '{PASS}' | sudo -S -p '' {body}"
    elif use_sudo_pw and not NEEDS_SUDO_PW:
        # Root: tira o "sudo " prefix, ja roda como root.
        cmd = cmd[5:] if cmd.startswith("sudo ") else cmd
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-2000:])
    if err and rc != 0:
        print(f"STDERR: {err[-2000:]}", file=sys.stderr)
    print(f"exit={rc}")
    return rc, out, err


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "test"

    auth_label = f"key={KEY_PATH}" if USE_KEY else "password"
    print(f"== Connecting to {USER}@{HOST} ({auth_label}) ==")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if USE_KEY:
        client.connect(
            HOST, username=USER, key_filename=KEY_PATH, timeout=30,
            allow_agent=False, look_for_keys=False,
        )
    else:
        client.connect(
            HOST, username=USER, password=PASS, timeout=30,
            allow_agent=False, look_for_keys=False,
        )
    print("CONNECTED")

    try:
        if action == "test":
            run(client, "uname -a")
            run(client, "lsb_release -a 2>/dev/null || cat /etc/os-release")
            run(client, "whoami; id; pwd")
            run(client, "df -h /")
            run(client, "free -h")
            run(client, "docker --version 2>&1 || echo 'docker not installed'")
            run(client, "nginx -v 2>&1 || echo 'nginx not installed'")
            run(client, "git --version 2>&1 || echo 'git not installed'")

        elif action == "bootstrap":
            # Instala nginx nativo + python3-cryptography. Pula em VPS que ja roda nginx-proxy em Docker.
            run(client, "sudo DEBIAN_FRONTEND=noninteractive apt install -y nginx python3-cryptography curl", use_sudo_pw=True, timeout=600)
            run(client, "sudo systemctl enable --now nginx", use_sudo_pw=True)
            run(client, "sudo ufw allow 22/tcp", use_sudo_pw=True)
            run(client, "sudo ufw allow 80/tcp", use_sudo_pw=True)
            run(client, "sudo ufw --force enable", use_sudo_pw=True)
            run(client, "docker --version")
            run(client, "docker compose version")
            run(client, "nginx -v 2>&1")

        elif action == "clone":
            run(client, "rm -rf ~/agentic-workflow-medallion-pipeline")
            run(client, "git clone https://github.com/RodrigoSiliunas/agentic-workflow-medallion-pipeline.git ~/agentic-workflow-medallion-pipeline", timeout=300)
            run(client, "cd ~/agentic-workflow-medallion-pipeline && git log --oneline -3")

        elif action == "env":
            base = "~/agentic-workflow-medallion-pipeline"
            run(client, f"cp {base}/.env.example {base}/.env")
            run(client, f"cp {base}/platform/backend/.env.example {base}/platform/backend/.env")
            # Gerar SECRET_KEY (token_hex 64)
            run(client, f'python3 -c "import secrets; print(\\"SECRET_KEY=\\" + secrets.token_hex(64))" >> {base}/platform/backend/.env')
            # Gerar ENCRYPTION_KEY (Fernet)
            run(client, f'python3 -c "from cryptography.fernet import Fernet; print(\\"ENCRYPTION_KEY=\\" + Fernet.generate_key().decode())" >> {base}/platform/backend/.env')
            # OMNI_API_KEY + NGROK_AUTHTOKEN pro compose nao reclamar de
            # ${VAR:?} em profiles nao usados (gpu/tunnel)
            run(client, f"echo 'OMNI_API_KEY=omni_dummy_key_replace_me' >> {base}/.env")
            run(client, f"echo 'NGROK_AUTHTOKEN=' >> {base}/.env")
            # Mostra resultado (sem creds reais — sao placeholders)
            run(client, f"cat {base}/.env")
            run(client, f"cat {base}/platform/backend/.env")

        elif action == "compose_override":
            base = "~/agentic-workflow-medallion-pipeline/platform/backend"
            # CORS_ORIGINS aponta pro proprio host do VPS — vem do env VPS_HOST
            override = f"""services:
  backend:
    environment:
      CORS_ORIGINS: '[\"http://{HOST}\"]'
  frontend:
    environment:
      NUXT_PUBLIC_API_BASE: /api/v1
      NUXT_PUBLIC_MOCK_MODE: \"false\"
"""
            sftp = client.open_sftp()
            sftp.chdir(".")
            # resolve home path
            _, out, _ = run(client, f"realpath {base}")
            real_path = out.strip()
            with sftp.file(f"{real_path}/docker-compose.override.yml", "w") as f:
                f.write(override)
            sftp.close()
            run(client, f"cat {base}/docker-compose.override.yml")

        elif action == "compose_up":
            base = "~/agentic-workflow-medallion-pipeline/platform/backend"
            run(client, f"cd {base} && docker compose up -d --build", timeout=900)
            time.sleep(5)
            run(client, f"cd {base} && docker compose ps")

        elif action == "compose_logs":
            base = "~/agentic-workflow-medallion-pipeline/platform/backend"
            run(client, f"cd {base} && docker compose logs --tail=100 backend")
            run(client, f"cd {base} && docker compose logs --tail=60 frontend")
            run(client, f"cd {base} && docker compose logs --tail=30 postgres redis")

        elif action == "nginx":
            # AVISO: conflita com nginx-proxy em Docker (porta 80). Apenas pra VPS sem reverse proxy nativo.
            nginx_conf = """server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 50M;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""
            # Escreve em /tmp e move com sudo
            sftp = client.open_sftp()
            with sftp.file("/tmp/flowertex.nginx.conf", "w") as f:
                f.write(nginx_conf)
            sftp.close()
            run(client, "sudo mv /tmp/flowertex.nginx.conf /etc/nginx/sites-available/flowertex", use_sudo_pw=True)
            run(client, "sudo ln -sf /etc/nginx/sites-available/flowertex /etc/nginx/sites-enabled/flowertex", use_sudo_pw=True)
            run(client, "sudo rm -f /etc/nginx/sites-enabled/default", use_sudo_pw=True)
            run(client, "sudo nginx -t", use_sudo_pw=True)
            run(client, "sudo systemctl reload nginx", use_sudo_pw=True)

        elif action == "verify":
            run(client, "curl -s -o /dev/null -w 'health: %{http_code}\\n' http://127.0.0.1/health")
            run(client, "curl -s -o /dev/null -w 'api templates: %{http_code}\\n' http://127.0.0.1/api/v1/templates")
            run(client, "curl -s -o /dev/null -w 'frontend: %{http_code}\\n' http://127.0.0.1/")
            run(client, "sudo docker compose -f ~/agentic-workflow-medallion-pipeline/platform/backend/docker-compose.yml ps", use_sudo_pw=True)

        elif action == "teardown":
            # Remove deploy completo: containers, volumes, networks, imagens, repo clonado, nginx site.
            base = "~/agentic-workflow-medallion-pipeline"
            run(client, f"cd {base}/platform/backend && docker compose down -v --remove-orphans 2>&1 || true", timeout=180)
            run(client, "docker ps -a --format '{{.Names}}' | grep -E '^flowertex-' | xargs -r docker rm -f")
            run(client, "docker volume ls --format '{{.Name}}' | grep -iE 'flowertex|backend' | xargs -r docker volume rm")
            run(client, "docker network ls --format '{{.Name}}' | grep -iE 'flowertex|backend' | xargs -r docker network rm")
            run(client, "docker images --format '{{.Repository}}:{{.Tag}}' | grep -iE '^backend-(backend|frontend|omni)' | xargs -r docker rmi")
            run(client, f"rm -rf {base}")
            run(client, "sudo rm -f /etc/nginx/sites-enabled/flowertex /etc/nginx/sites-available/flowertex", use_sudo_pw=True)
            run(client, "sudo ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default 2>&1 || true", use_sudo_pw=True)
            run(client, "sudo nginx -t 2>&1 && sudo systemctl reload nginx", use_sudo_pw=True)
            run(client, "docker ps -a --format '{{.Names}}\\t{{.Status}}' | grep -E 'flowertex' || echo 'clean: no flowertex containers'")

        else:
            print(f"unknown action: {action}")
            sys.exit(2)

    finally:
        client.close()
        print("\n== closed ==")


if __name__ == "__main__":
    main()
