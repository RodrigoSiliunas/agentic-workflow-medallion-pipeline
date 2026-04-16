plugin "aws" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

config {
  format              = "compact"
  module              = false
  disabled_by_default = false
}

# Regras recomendadas permanecem ligadas. Override explicit se precisar
# silenciar algo no futuro.
