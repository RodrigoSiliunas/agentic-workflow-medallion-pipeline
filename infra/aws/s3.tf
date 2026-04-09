# =============================================================================
# S3 Data Lake — Medallion Pipeline
# Estrutura: bronze/ | silver/ | gold/ | pipeline/ | checkpoints/ | _logs/
# =============================================================================

resource "aws_s3_bucket" "datalake" {
  bucket = var.bucket_name

  tags = {
    CostCenter = "pipeline-001"
    DataLayer  = "datalake"
  }
}

# --- Versionamento (requisito Delta Lake time travel) ---
resource "aws_s3_bucket_versioning" "datalake" {
  bucket = aws_s3_bucket.datalake.id
  versioning_configuration {
    status = "Enabled"
  }
}

# --- Encryption SSE-S3 com bucket key ---
resource "aws_s3_bucket_server_side_encryption_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# --- Block public access ---
resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- ACLs desabilitadas (bucket owner enforced) ---
resource "aws_s3_bucket_ownership_controls" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# --- Server access logging ---
resource "aws_s3_bucket_logging" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  target_bucket = aws_s3_bucket.datalake.id
  target_prefix = "_logs/"
}

# =============================================================================
# Lifecycle Rules — otimizacao de custo por camada
# =============================================================================

resource "aws_s3_bucket_lifecycle_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  # Bronze: Intelligent-Tiering apos 30 dias
  rule {
    id     = "bronze-tiering"
    status = "Enabled"

    filter {
      prefix = "bronze/"
    }

    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }
  }

  # Checkpoints: deletar apos 90 dias
  rule {
    id     = "checkpoints-cleanup"
    status = "Enabled"

    filter {
      prefix = "checkpoints/"
    }

    expiration {
      days = 90
    }
  }

  # Logs: Glacier apos 90 dias, deletar apos 365
  rule {
    id     = "logs-archive"
    status = "Enabled"

    filter {
      prefix = "_logs/"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }

  # Versoes anteriores: deletar apos 30 dias (todas as camadas)
  rule {
    id     = "noncurrent-cleanup"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  # Incomplete multipart uploads: cleanup apos 7 dias
  rule {
    id     = "abort-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# =============================================================================
# Estrutura de pastas (objetos vazios como prefixos)
# =============================================================================

resource "aws_s3_object" "folders" {
  for_each = toset(["bronze/", "silver/", "gold/", "pipeline/", "checkpoints/"])

  bucket  = aws_s3_bucket.datalake.id
  key     = each.value
  content = ""
}
