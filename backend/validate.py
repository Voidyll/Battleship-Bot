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

