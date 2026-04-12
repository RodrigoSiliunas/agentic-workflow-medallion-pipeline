FROM oven/bun:1-alpine

# Deps + PostgreSQL nativo (workaround: Omni ignora DATABASE_URL externo
# e sempre tenta embedded pgserve que espera binarios em linux-x64/bin/)
RUN apk add --no-cache python3 make g++ git curl bash \
    postgresql postgresql-client su-exec

# Usuario nao-root (initdb recusa rodar como root)
RUN addgroup -S omni && adduser -S omni -G omni -h /home/omni

# Instalar omni e pm2 globalmente (como root)
RUN bun add -g @automagik/omni pm2

# Tornar bun global acessivel para o user omni
RUN chmod 755 /root && chmod -R a+rX /root/.bun

# COPIAR binarios PostgreSQL (nao symlink — pgserve faz chmod que falha em symlinks)
RUN mkdir -p /home/omni/.pgserve/bin/linux-x64/bin && \
    cp /usr/bin/initdb /home/omni/.pgserve/bin/linux-x64/bin/initdb && \
    cp /usr/bin/pg_ctl /home/omni/.pgserve/bin/linux-x64/bin/pg_ctl && \
    cp /usr/bin/postgres /home/omni/.pgserve/bin/linux-x64/bin/postgres && \
    cp /usr/bin/pg_isready /home/omni/.pgserve/bin/linux-x64/bin/pg_isready && \
    chmod 755 /home/omni/.pgserve/bin/linux-x64/bin/*

# Copiar shared libs do PostgreSQL (necessario pra binarios copiados)
RUN cp -r /usr/lib/postgresql* /home/omni/.pgserve/lib/ 2>/dev/null || true && \
    cp -r /usr/share/postgresql /home/omni/.pgserve/share/ 2>/dev/null || true

# Diretorio de dados do omni
RUN mkdir -p /home/omni/.omni/data && \
    chown -R omni:omni /home/omni

VOLUME /home/omni/.omni/data
EXPOSE 8882

HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=10 \
  CMD curl -sf http://localhost:8882/api/v2/health || exit 1

ENV OMNI_PORT=8882
ENV OMNI_API_KEY=changeme
ENV HOME=/home/omni
ENV PATH="/root/.bun/bin:$PATH"

COPY omni-entrypoint.sh /usr/local/bin/omni-entrypoint.sh
RUN chmod +x /usr/local/bin/omni-entrypoint.sh

CMD ["/usr/local/bin/omni-entrypoint.sh"]
