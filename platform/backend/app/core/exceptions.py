"""Domain exceptions mapeadas para HTTP status codes."""


class AppError(Exception):
    status_code: int = 500
    detail: str = "Erro interno"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Recurso nao encontrado"


class ConflictError(AppError):
    status_code = 409
    detail = "Conflito"


class ValidationError(AppError):
    status_code = 422
    detail = "Dados invalidos"


class AuthorizationError(AppError):
    status_code = 403
    detail = "Sem permissao"


class AuthenticationError(AppError):
    status_code = 401
    detail = "Nao autenticado"


class ExternalServiceError(AppError):
    status_code = 502
    detail = "Erro no servico externo"


class RateLimitError(AppError):
    status_code = 429
    detail = "Limite de requisicoes excedido"
