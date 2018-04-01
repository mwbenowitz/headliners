#
# These are various functions that are repeated around headliner
# Easier to maintain in one place obviously
#

def validateString(str):
    if not str or str == ' ' or str == '':
        return False
    elif len(str) < 13:
        return False
    return True
