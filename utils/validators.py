import re


def only_digits(value: str) -> str:
    """Remove todos os caracteres nao numericos de uma string."""
    return re.sub(r"\D", "", value or "")


def format_cnpj(value: str) -> str:
    """Aplica mascara padrao de CNPJ: 00.000.000/0000-00."""
    digits = only_digits(value)
    if len(digits) > 14:
        digits = digits[:14]

    if len(digits) <= 2:
        return digits
    if len(digits) <= 5:
        return f"{digits[:2]}.{digits[2:]}"
    if len(digits) <= 8:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:]}"
    if len(digits) <= 12:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:]}"
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def _calculate_digit(base_digits: str, multipliers: list[int]) -> str:
    """Calcula um digito verificador de CNPJ para uma base numerica."""
    total = sum(int(d) * m for d, m in zip(base_digits, multipliers))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)


def is_valid_cnpj(value: str) -> bool:
    """Valida CNPJ pelo algoritmo oficial de digitos verificadores."""
    digits = only_digits(value)

    if len(digits) != 14:
        return False

    if digits == digits[0] * 14:
        return False

    first_multipliers = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_multipliers = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    first_digit = _calculate_digit(digits[:12], first_multipliers)
    second_digit = _calculate_digit(digits[:12] + first_digit, second_multipliers)

    return digits[-2:] == first_digit + second_digit
