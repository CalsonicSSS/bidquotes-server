from fastapi import HTTPException, status


class UserNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


class ContactInfoNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Contact information not found")


class DatabaseError(HTTPException):
    def __init__(self, error_detail_message: str):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail_message)


class ServerError(HTTPException):
    def __init__(self, error_detail_message: str):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail_message)


class ValidationError(HTTPException):
    def __init__(self, error_detail_message: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail_message)
