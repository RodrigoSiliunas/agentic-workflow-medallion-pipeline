"""Contratos de schema para o pipeline Medallion."""

REQUIRED_COLUMNS: set[str] = {
    "message_id",
    "conversation_id",
    "timestamp",
    "direction",
    "sender_phone",
    "sender_name",
    "message_type",
    "message_body",
    "status",
    "channel",
    "campaign_id",
    "agent_id",
    "conversation_outcome",
    "metadata",
}

VALUE_CONSTRAINTS: dict[str, set[str] | str] = {
    "conversation_id": r"^conv_[0-9a-f]{8}$",
    "direction": {"inbound", "outbound"},
    "message_type": {
        "text",
        "audio",
        "image",
        "document",
        "sticker",
        "contact",
        "video",
        "location",
    },
    "status": {"sent", "delivered", "read", "failed"},
    "channel": {"whatsapp"},
}
