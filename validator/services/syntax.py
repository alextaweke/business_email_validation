from email_validator import validate_email, EmailNotValidError

def normalize_and_validate(email: str) -> tuple[bool, str | None, str | None]:
    """
    Returns (valid, normalized_address, reason_code).
    DNS is intentionally not checked here; DNS resolution is a separate stage.
    Domain is IDNA-normalized/lowercased by email-validator. The local part is not
    deliberately lowercased for identity comparisons.
    """
    try:
        result = validate_email(
            email,
            check_deliverability=False,
            allow_smtputf8=False,
            allow_quoted_local=False,
            allow_domain_literal=False,
        )
        return True, result.normalized, None
    except EmailNotValidError:
        return False, None, "INVALID_SYNTAX"
