class TIDEAPIException(Exception):
    def __init__(self, *args):
        super().__init__(*args)
        
    def __repr__(self) -> str:
        return type(self).__name__

class APILookupError(TIDEAPIException):
    '''Use when an in-memory TIDE-API look up fails.'''
    pass

class TraceLookupError(TIDEAPIException):
    '''Use when a TIDE query succeeds but the requested object does not exist'''    
    pass

class InternalExceptionError(TIDEAPIException):
    '''Use when internal/backend logic fails'''
    pass

class DataValidationError(TIDEAPIException):
    '''Use when data is deemed invalid for whatever reason'''
    pass