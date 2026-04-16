# =============================================================================
# Security — VPC Security Group + KMS Key
# =============================================================================

# --- Data source: VPC default (para security group) ---
data "aws_vpc" "default" {
  default = true
}

# --- Security Group: Pipeline Services ---
# Para servicos que precisam acessar Databricks/AWS APIs
resource "aws_security_group" "pipeline_services" {
  name        = "${var.project_name}-pipeline-services"
  description = "Security group para servicos do pipeline (backend, workers)"
  vpc_id      = data.aws_vpc.default.id

  # Outbound: HTTPS para APIs externas (Databricks, GitHub, Anthropic)
  egress {
    description = "HTTPS outbound para APIs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound: PostgreSQL (para RDS se migrar do Docker)
  egress {
    description = "PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  # Outbound: Redis (para ElastiCache se migrar do Docker)
  egress {
    description = "Redis"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  tags = {
    Purpose = "pipeline-services"
  }
}

# --- Security Group: Backend API ---
#
# T3: removido ingress 8000/tcp 0.0.0.0/0 — FastAPI deve rodar atras de
# ALB. HTTP (80) existe apenas para redirect ao 443; em producao final,
# preferivel deixar somente 443.
resource "aws_security_group" "backend_api" {
  name        = "${var.project_name}-backend-api"
  description = "Security group para a API FastAPI (HTTP->HTTPS redirect + HTTPS)"
  vpc_id      = data.aws_vpc.default.id

  # Inbound: HTTP — apenas para responder redirect 301 -> HTTPS.
  ingress {
    description = "HTTP (redirect-only em prod)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Inbound: HTTPS.
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound: all
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Purpose = "backend-api"
  }
}

# --- Security Group: Database ---
resource "aws_security_group" "database" {
  name        = "${var.project_name}-database"
  description = "Security group para PostgreSQL + Redis (apenas acesso interno)"
  vpc_id      = data.aws_vpc.default.id

  # Inbound: PostgreSQL apenas do backend
  ingress {
    description     = "PostgreSQL from backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend_api.id]
  }

  # Inbound: Redis apenas do backend
  ingress {
    description     = "Redis from backend"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.backend_api.id]
  }

  # Outbound: nenhum (apenas recebe conexoes)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Purpose = "database"
  }
}
