def check_integer_format(text: str):
    """Only accepts positive integers."""
    if text == '':
        return True
    elif all(x in '0123456789' for x in text):
        try:
            int(text)
            return True
        except ValueError:
            return False
    else:
        return False

def check_float_format(text: str):
    """Only accepts positive floats."""
    if text == '':
        return True
    elif all(x in '0123456789.' for x in text) and text.count('.') <= 1:
        try:
            float(text)
            return True
        except ValueError:
            return False
    else:
        return False