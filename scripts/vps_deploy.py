"""SSH bootstrap + deploy do projeto no VPS via paramiko.

Roda comandos remotos com password auth, captura stdout/stderr/exit code.

Credenciais via env vars (NUNCA hardcoded):
  VPS_HOST   — IP/hostname do VPS
  VPS_USER   — usuario SSH
  VPS_PASS   — password SSH

Uso:
  $env:VPS_HOST="x.x.x.x"; $env:VPS_USER="user"; $env:VPS_PASS="..."
  python scripts/vps_deploy.py <action>
"""

from __future__ import annotations

import io
import os
import sys
import time

import paramiko

# Forca stdout UTF-8 pra acentos/unicode do apt nao quebrarem em Windows cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HOST = os.environ.get("VPS_HOST")
USER = os.environ.get("VPS_USER")
PASS = os.environ.get("VPS_PASS")

if not (HOST and USER and PASS):
    sys.exit("ERROR: defina VPS_HOST, VPS_USER e VPS_PASS no ambiente antes de rodar.")


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600, use_sudo_pw: bool = False) -> tuple[int, str, str]:
    """Run remote command. Returns (exit_code, stdout, stderr)."""
    print(f"\n>>> {cmd[:200]}")
    if use_sudo_pw:
        # Inject password pra sudo via stdin (-S flag)
        cmd = f"echo '{PASS}' | sudo -S -p '' {cmd[5:] if cmd.startswith('sudo ') else cmd}"
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

    print(f"== Connecting to {USER}@{HOST} ==")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30, allow_agent=False, look_for_keys=False)
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
            # Docker, git, ufw ja instalados. Falta nginx + python3-cryptography.
            run(client, "sudo -S DEBIAN_FRONTEND=noninteractive apt install -y nginx python3-cryptography curl", use_sudo_pw=True, timeout=600)
            run(client, "sudo -S systemctl enable --now nginx", use_sudo_pw=True)
            run(client, "sudo -S ufw allow 22/tcp", use_sudo_pw=True)
            run(client, "sudo -S ufw allow 80/tcp", use_sudo_pw=True)
            run(client, "sudo -S ufw --force enable", use_sudo_pw=True)
            run(client, "docker --version", use_sudo_pw=False)
            run(client, "docker compose version", use_sudo_pw=False)
            run(client, "nginx -v 2>&1", use_sudo_pw=False)

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
            # contabo ja no grupo docker (id mostrou 988), sem sudo
            run(client, f"cd {base} && docker compose up -d --build", timeout=900)
            time.sleep(5)
            run(client, f"cd {base} && docker compose ps")

        elif action == "compose_logs":
            base = "~/agentic-workflow-medallion-pipeline/platform/backend"
            run(client, f"cd {base} && docker compose logs --tail=100 backend")
            run(client, f"cd {base} && docker compose logs --tail=60 frontend")
            run(client, f"cd {base} && docker compose logs --tail=30 postgres redis")

        elif action == "nginx":
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
            run(client, "sudo -S mv /tmp/flowertex.nginx.conf /etc/nginx/sites-available/flowertex", use_sudo_pw=True)
            run(client, "sudo -S ln -sf /etc/nginx/sites-available/flowertex /etc/nginx/sites-enabled/flowertex", use_sudo_pw=True)
            run(client, "sudo -S rm -f /etc/nginx/sites-enabled/default", use_sudo_pw=True)
            run(client, "sudo -S nginx -t", use_sudo_pw=True)
            run(client, "sudo -S systemctl reload nginx", use_sudo_pw=True)

        elif action == "verify":
            run(client, "curl -s -o /dev/null -w 'health: %{http_code}\\n' http://127.0.0.1/health")
            run(client, "curl -s -o /dev/null -w 'api templates: %{http_code}\\n' http://127.0.0.1/api/v1/templates")
            run(client, "curl -s -o /dev/null -w 'frontend: %{http_code}\\n' http://127.0.0.1/")
            run(client, "sudo -S docker compose -f ~/agentic-workflow-medallion-pipeline/platform/backend/docker-compose.yml ps", use_sudo_pw=True)

        else:
            print(f"unknown action: {action}")
            sys.exit(2)

    finally:
        client.close()
        print("\n== closed ==")


if __name__ == "__main__":
    main()
