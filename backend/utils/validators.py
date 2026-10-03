import re

PASSWORD_MIN_LENGTH = 8

def validate_password(password):
    """Valida contraseña. Retorna (ok, mensaje_error)."""
    if not password or not isinstance(password, str):
        return False, "La contraseña es requerida"
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres"
    if len(password) > 128:
        return False, "La contraseña es demasiado larga (máx 128)"
    # Al menos una letra y un número para no permitir 12345678 solo números repetidos
    # Mantenemos regla suave: no exigir mayúscula/especial para no complicar a usuarios del conservatorio
    has_letter = bool(re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", password))
    has_number = bool(re.search(r"[0-9]", password))
    if not (has_letter and has_number):
        return False, "La contraseña debe contener al menos una letra y un número"
    if password.strip() != password:
        return False, "La contraseña no puede empezar o terminar con espacios"
    # Evitar contraseñas ultra comunes
    common = {"password", "12345678", "admin123", "qwerty123", "123456789"}
    if password.lower() in common:
        return False, "Esa contraseña es demasiado común, elija otra más segura"
    return True, None

def validate_email_format(email):
    if not email or not isinstance(email, str):
        return False, "Email requerido"
    email = email.strip()
    # Validación básica + intentar usar email-validator si está instalado
    try:
        from email_validator import validate_email, EmailNotValidError
        validate_email(email, check_deliverability=False)
        return True, None
    except ImportError:
        pass
    except Exception as e:
        return False, str(e)
    # fallback regex
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "Formato de email inválido"
    return True, None

def validate_cedula(cedula):
    if not cedula or not isinstance(cedula, str):
        return False, "Cédula requerida"
    cedula = cedula.strip()
    if not re.match(r"^V-\d{6,9}$", cedula) and not re.match(r"^E-\d{6,9}$", cedula):
        # Permitir también sin prefijo para compatibilidad, pero avisar
        if not re.match(r"^\d{6,9}$", cedula):
            return False, "Formato de cédula inválido. Use V-12345678"
    return True, None
