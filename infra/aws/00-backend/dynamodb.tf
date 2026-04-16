# =============================================================================
# DynamoDB — Lock concorrente do Terraform
# =============================================================================
#
# Schema fixo pelo Terraform: PK chamada `LockID` do tipo string.
# PAY_PER_REQUEST evita custo fixo em workspaces idle.
# =============================================================================

resource "aws_dynamodb_table" "terraform_locks" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.tfstate.arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Purpose = "terraform-state-lock"
  }
}
