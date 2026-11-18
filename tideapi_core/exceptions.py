'''
    TIDE-API CUSTOM EXCEPTIONS
'''
class TIDEAPIException(Exception):
    '''Base class for TIDE-API Exceptions'''
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __repr__(self) -> str:
        return type(self).__name__

class APILookupError(TIDEAPIException):
    '''Use when an in-memory TIDE-API look up fails.'''
    pass

class APIStoreLookupError(TIDEAPIException):
    '''Use when TIDEAPIStore look up fails'''

class TraceLookupError(TIDEAPIException):
    '''Use when a TIDE query succeeds but the requested object does not exist'''
    pass

class InternalExceptionError(TIDEAPIException):
    '''Use when internal/backend logic fails'''
    pass

class DataValidationError(TIDEAPIException):
    '''Use when data is deemed invalid for whatever reason'''
    pass

class AlreadyRegisteredError(TIDEAPIException):
    '''Use when an item already exists upon registration of it'''
    pass

class InvalidAPIStoreConfigurationError(TIDEAPIException):
    '''Use when a TIDEAPI Store fails to configure or its configuration is invalid'''
    pass
