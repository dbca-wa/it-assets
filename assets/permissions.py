from rest_framework import permissions

class IsAdminUserorReadOnly(permissions.BasePermission):
    """
    Allows access only to staff users.
    """
    def has_permission(self, request, view):

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user and request.user.is_staff