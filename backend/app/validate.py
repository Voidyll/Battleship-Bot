from flask import abort

class Validation:
    def __init__(self, missingHeaders: list[str] = None):
        self._missingHeaders = missingHeaders

        self._success = len(self._missingHeaders) == 0

    @property
    def success(self):
        return self._success
    
    @property
    def missingHeaders(self):
        return self._missingHeaders

def validateInput(data:dict, headers:list) -> Validation:
    missingHeaders = list()

    if data is None:
        return False

    for header in headers:
        if (data.get(header) == None):
            missingHeaders.append(header)
        
    return Validation(missingHeaders)

def validateInt(name, data) -> int:
    try:
        return int(data)
    except:
        abort(400, description="Invalid input. Must be integer for " + name + ".")

def validateBool(name, data) -> bool:
    try:
        return bool(data)
    except:
        abort(400, description="Invalid input. Must be boolean for " + name)