from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny

ALLOWED_ANONYMOUS_VIEWS = {
    "RegisterView",
    "TokenObtainPairView",
    "TokenRefreshView",
    "PopularSearchesView",
    "PasswordResetRequestView",
    "PasswordResetConfirmView",
    "EmailVerificationConfirmView",
    "HealthCheckView",
    "CategoryViewSet",
    "AmenityViewSet",
    "SpectacularAPIView",
    "SpectacularSwaggerView",
}


def iter_view_classes(patterns=None):
    """Recursively walk the URLconf and yield every DRF view class it routes to."""
    if patterns is None:
        patterns = get_resolver().url_patterns
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from iter_view_classes(entry.url_patterns)
        elif isinstance(entry, URLPattern):
            view_class = getattr(entry.callback, "cls", None)
            if view_class is not None:
                yield view_class


class PermissionAuditTests(SimpleTestCase):
    """
    Guards against a view silently allowing anonymous access.

    DRF's DEFAULT_PERMISSION_CLASSES (IsAuthenticated) already makes "forgetting" a
    permission_classes attribute safe - it deny-by-defaults. The actual risk is the opposite: a
    view explicitly declaring AllowAny (or an empty permission_classes) where it shouldn't. This
    test enumerates every routed view and fails if a new one opens up without being added to
    ALLOWED_ANONYMOUS_VIEWS, forcing that decision through code review.
    """

    def test_only_whitelisted_views_allow_anonymous_access(self):
        unexpected_open_views = []
        for view_class in iter_view_classes():
            permission_classes = getattr(view_class, "permission_classes", None)
            if permission_classes is None:
                continue
            is_open = len(permission_classes) == 0 or AllowAny in permission_classes
            if is_open and view_class.__name__ not in ALLOWED_ANONYMOUS_VIEWS:
                unexpected_open_views.append(view_class.__name__)

        self.assertEqual(
            unexpected_open_views,
            [],
            f"View(s) allow anonymous access without being whitelisted: {unexpected_open_views}. "
            "If this is intentional, add the view name to ALLOWED_ANONYMOUS_VIEWS.",
        )

    def test_whitelist_has_no_stale_entries(self):
        routed_view_names = {view_class.__name__ for view_class in iter_view_classes()}
        stale_entries = ALLOWED_ANONYMOUS_VIEWS - routed_view_names
        self.assertEqual(
            stale_entries,
            set(),
            f"ALLOWED_ANONYMOUS_VIEWS references view(s) no longer routed: {stale_entries}.",
        )
