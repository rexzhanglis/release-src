class ValidationException(Exception):
    message = None

    def __init__(self, msg):
        ValidationException.message = msg


class CustomRuntimeException(Exception):
    message = None

    def __init__(self, msg):
        CustomRuntimeException.message = msg

class NoPermissionException(Exception):
    message = "该用户没有权限，只有创建该用户的人才有此操作权限"
