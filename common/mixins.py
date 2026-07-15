from rest_framework.permissions import IsAuthenticated


class ActionPermissionsMixin:
    """
    Resolves ``get_permissions()`` from a ``permission_classes_by_action`` dict keyed by
    ``self.action``, instead of each viewset hand-rolling the same if/elif chain.
    """

    permission_classes_by_action: dict = {}
    default_permission_classes = [IsAuthenticated]

    def get_permissions(self) -> list:
        permission_classes = self.permission_classes_by_action.get(
            self.action, self.default_permission_classes
        )
        return [permission() for permission in permission_classes]
