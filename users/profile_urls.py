from django.urls import path

from users.views import (
    AccountDeletionView,
    AgentProfileView,
    CertifyAgentProfileView,
    ChangePasswordView,
    EmailVerificationRequestView,
    OwnerProfileView,
    TenantProfileView,
    UserProfileView,
    VerifyOwnerProfileView,
)

app_name = "users"

urlpatterns = [
    path("me/", UserProfileView.as_view(), name="user-profile"),
    path("me/password/", ChangePasswordView.as_view(), name="change-password"),
    path(
        "me/email-verification/request/",
        EmailVerificationRequestView.as_view(),
        name="email-verification-request",
    ),
    path("me/delete-account/", AccountDeletionView.as_view(), name="delete-account"),
    path("me/owner-profile/", OwnerProfileView.as_view(), name="owner-profile"),
    path("me/agent-profile/", AgentProfileView.as_view(), name="agent-profile"),
    path("me/tenant-profile/", TenantProfileView.as_view(), name="tenant-profile"),
    path(
        "<int:user_id>/owner-profile/verify/",
        VerifyOwnerProfileView.as_view(),
        name="owner-profile-verify",
    ),
    path(
        "<int:user_id>/agent-profile/certify/",
        CertifyAgentProfileView.as_view(),
        name="agent-profile-certify",
    ),
]
