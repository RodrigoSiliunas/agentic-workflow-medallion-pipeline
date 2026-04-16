# =============================================================================
# IAM Policies — Reusaveis entre users e roles
# =============================================================================

# --- S3 Data Lake Access (Databricks) ---
resource "aws_iam_policy" "databricks_s3_access" {
  name        = "${var.project_name}-databricks-s3-access"
  description = "Permite Databricks acessar o data lake S3 (leitura, escrita, listagem)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*",
        ]
      },
      {
        Sid    = "S3ListAll"
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation",
        ]
        Resource = "arn:aws:s3:::*"
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# --- S3 Pipeline Access (para CI/CD user e agent role) ---
resource "aws_iam_policy" "pipeline_s3_access" {
  name        = "${var.project_name}-pipeline-s3-access"
  description = "Acesso S3 para pipeline (upload dados, leitura resultados)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3FullAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetObjectVersion",
          "s3:ListBucketVersions",
        ]
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*",
        ]
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# --- Secrets Manager Read (para ler credenciais) ---
resource "aws_iam_policy" "pipeline_secrets_read" {
  name        = "${var.project_name}-secrets-read"
  description = "Leitura de secrets do pipeline no Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/*"
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# --- STS para Databricks (pass role + self-assume) ---
resource "aws_iam_policy" "databricks_sts" {
  name        = "${var.project_name}-databricks-sts"
  description = "Permite Databricks criar sessoes temporarias e self-assume (requisito Unity Catalog)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSelfAssume"
        Effect = "Allow"
        Action = [
          "sts:AssumeRole",
          "sts:TagSession",
        ]
        Resource = "arn:aws:iam::${local.account_id}:role/service-roles/${var.project_name}-databricks-role"
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# Attach STS policy ao Databricks role
resource "aws_iam_role_policy_attachment" "databricks_sts" {
  role       = aws_iam_role.databricks_cross_account.name
  policy_arn = aws_iam_policy.databricks_sts.arn
}

# --- EC2/VPC para Databricks criar clusters e gerenciar rede ---
resource "aws_iam_policy" "databricks_ec2_vpc" {
  name        = "${var.project_name}-databricks-ec2-vpc"
  description = "Permissoes EC2/VPC para Databricks gerenciar clusters e networking"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2Instances"
        Effect = "Allow"
        Action = [
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeVolumes",
          "ec2:DescribeRouteTables",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs",
          "ec2:DescribeImages",
          "ec2:DescribeSpotPriceHistory",
          "ec2:DescribeSpotInstanceRequests",
          "ec2:DescribeFleetInstances",
          "ec2:RunInstances",
          "ec2:TerminateInstances",
          "ec2:CreateTags",
          "ec2:DeleteTags",
          "ec2:RequestSpotInstances",
          "ec2:CancelSpotInstanceRequests",
          "ec2:CreateFleet",
          "ec2:DeleteFleet",
        ]
        Resource = "*"
      },
      {
        Sid    = "VPCManagement"
        Effect = "Allow"
        Action = [
          "ec2:CreateVpc",
          "ec2:DeleteVpc",
          "ec2:CreateSubnet",
          "ec2:DeleteSubnet",
          "ec2:CreateInternetGateway",
          "ec2:DeleteInternetGateway",
          "ec2:AttachInternetGateway",
          "ec2:DetachInternetGateway",
          "ec2:CreateNatGateway",
          "ec2:DeleteNatGateway",
          "ec2:DescribeNatGateways",
          "ec2:CreateRouteTable",
          "ec2:DeleteRouteTable",
          "ec2:CreateRoute",
          "ec2:DeleteRoute",
          "ec2:AssociateRouteTable",
          "ec2:DisassociateRouteTable",
          "ec2:AllocateAddress",
          "ec2:ReleaseAddress",
          "ec2:DescribeAddresses",
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:CreateVpcEndpoint",
          "ec2:DeleteVpcEndpoints",
          "ec2:DescribeVpcEndpoints",
          "ec2:ModifyVpcAttribute",
        ]
        Resource = "*"
      },
      {
        Sid      = "IAMPassRole"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = "arn:aws:iam::${local.account_id}:role/service-roles/${var.project_name}-*"
      },
      {
        Sid      = "IAMCreateServiceLinkedRole"
        Effect   = "Allow"
        Action   = "iam:CreateServiceLinkedRole"
        Resource = "arn:aws:iam::*:role/aws-service-role/spot.amazonaws.com/AWSServiceRoleForEC2Spot"
        Condition = {
          StringEquals = {
            "iam:AWSServiceName" = "spot.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# Attach EC2/VPC policy ao Databricks role
resource "aws_iam_role_policy_attachment" "databricks_ec2_vpc" {
  role       = aws_iam_role.databricks_cross_account.name
  policy_arn = aws_iam_policy.databricks_ec2_vpc.arn
}

# --- S3 Root Storage para Databricks ---
resource "aws_iam_policy" "databricks_root_storage" {
  name        = "${var.project_name}-databricks-root-storage"
  description = "Acesso ao bucket root do Databricks (assets, libs, logs)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RootStorageAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [
          "arn:aws:s3:::${var.databricks_root_bucket}",
          "arn:aws:s3:::${var.databricks_root_bucket}/*",
        ]
      }
    ]
  })

  tags = {
    CostCenter = "pipeline-001"
  }
}

# Attach root storage policy ao Databricks role
resource "aws_iam_role_policy_attachment" "databricks_root_storage" {
  role       = aws_iam_role.databricks_cross_account.name
  policy_arn = aws_iam_policy.databricks_root_storage.arn
}
