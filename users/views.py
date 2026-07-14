from django.db import IntegrityError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView, GenericAPIView, RetrieveUpdateAPIView, get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from users.models.agent import AgentProfile
from users.models.owner import OwnerProfile
from users.permissions import IsModerator
from users.serializers import (
    AccountDeletionSerializer,
    AgentProfileSerializer,
    ChangePasswordSerializer,
    EmailVerificationConfirmSerializer,
    EmailVerificationRequestSerializer,
    LogoutSerializer,
    OwnerProfileSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    TenantProfileSerializer,
    UserProfileSerializer,
)
from users.services.anonymization import anonymize_user
from users.services.email import send_email_verification_email, send_password_reset_email
from users.tokens import (
    email_verification_token_generator,
    encode_uid,
    password_reset_token_generator,
    set_password_and_revoke_sessions,
)


class RegisterView(CreateAPIView):
    """Public self-registration endpoint (AllowAny), rate-limited to curb account-spam/bruteforce."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'


class LogoutView(GenericAPIView):
    """Blacklists the given refresh token, ending the current session."""

    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request: Request) -> Response:
        """
        :param request: must carry a JSON body with a ``refresh`` token belonging to the caller.
        :return: 205 on success, 400 if the token is missing/invalid.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": _("Invalid or already blacklisted refresh token.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class PasswordResetRequestView(GenericAPIView):
    """
    Public endpoint requesting a password-reset email.

    Always responds 200 regardless of whether the email belongs to an account, to avoid leaking
    which emails are registered. Rate-limited to curb brute-force/spam use.
    """

    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request: Request) -> Response:
        """
        :param request: JSON body with an ``email``.
        :return: 200 always.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        if user is not None:
            token = password_reset_token_generator.make_token(user)
            send_password_reset_email(user, encode_uid(user), token)

        return Response(status=status.HTTP_200_OK)


class PasswordResetConfirmView(GenericAPIView):
    """Public endpoint completing a password reset given a valid uid+token from the email link."""

    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request: Request) -> Response:
        """
        :param request: JSON body with ``uid``, ``token``, ``new_password``.
        :return: 200 on success, 400 if the link is invalid/expired or the password fails validation.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        set_password_and_revoke_sessions(user, serializer.validated_data["new_password"])
        return Response(status=status.HTTP_200_OK)


class ChangePasswordView(GenericAPIView):
    """Authenticated endpoint for changing one's own password (current + new)."""

    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request: Request) -> Response:
        """
        :param request: JSON body with ``current_password``, ``new_password``.
        :return: 200 on success, 400 if the current password is wrong or the new one fails validation.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        set_password_and_revoke_sessions(request.user, serializer.validated_data["new_password"])
        return Response(status=status.HTTP_200_OK)


class EmailVerificationRequestView(GenericAPIView):
    """
    Authenticated endpoint that (re)sends a verification email for the caller's own address.

    No request body needed - unlike password reset, the caller is already identified via their
    access token, so there's no email-enumeration concern to guard against here.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = EmailVerificationRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'email_verification'

    def post(self, request: Request) -> Response:
        """
        :param request: authenticated; no body required.
        :return: 200 always. No-ops (without sending another email) if already verified.
        """
        user = request.user
        if not user.is_email_verified:
            token = email_verification_token_generator.make_token(user)
            send_email_verification_email(user, encode_uid(user), token)
        return Response(status=status.HTTP_200_OK)


class EmailVerificationConfirmView(GenericAPIView):
    """Public endpoint completing email verification given a valid uid+token from the email link."""

    permission_classes = [AllowAny]
    serializer_class = EmailVerificationConfirmSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'email_verification'

    def post(self, request: Request) -> Response:
        """
        :param request: JSON body with ``uid``, ``token``.
        :return: 200 on success, 400 if the link is invalid/expired.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return Response(status=status.HTTP_200_OK)


class AccountDeletionView(GenericAPIView):
    """
    GDPR Art. 17 right-to-erasure endpoint: anonymizes the caller's own account.

    Not a hard delete - Booking.tenant/Ticket.user are on_delete=PROTECT (German tax/commercial
    law requires retaining that transactional history), so personal fields are scrubbed instead
    (see users/services/anonymization.py::anonymize_user for the full field-by-field breakdown).
    Requires re-entering the password since this is irreversible.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AccountDeletionSerializer

    def post(self, request: Request) -> Response:
        """
        :param request: JSON body with ``password`` (the caller's current password).
        :return: 200 on success, 400 if the password is wrong.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        anonymize_user(request.user)
        return Response(status=status.HTTP_200_OK)


class UserProfileView(RetrieveUpdateAPIView):
    """API endpoint that allows authenticated users to view and update their own profile."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    queryset = User.objects.all()

    def get_object(self):
        """
        :return: the authenticated request user, regardless of any URL lookup.
        """
        return self.request.user


class SelfProfileView(APIView):
    """
    Shared GET/POST/PATCH behaviour for a user's own role profile (OwnerProfile/AgentProfile/
    TenantProfile) - the profile's primary key *is* the user (OneToOneField(primary_key=True)),
    so "self" fully identifies which row, with no separate lookup needed.

    Subclasses set ``related_name`` (the reverse accessor on User, e.g. "owner_profile") and
    ``role_check``/``role_error`` for the flag required to create one (Tenant has none - any
    authenticated user may create a TenantProfile).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = None
    related_name = None
    role_error = _("You do not have the required role for this profile.")

    @staticmethod
    def role_check(user: User) -> bool:
        return True

    def get_object(self):
        return getattr(self.request.user, self.related_name, None)

    def get(self, request: Request) -> Response:
        """:return: 200 with the profile, or 404 if the caller hasn't created one yet."""
        profile = self.get_object()
        if profile is None:
            raise NotFound()
        return Response(self.serializer_class(profile).data)

    def post(self, request: Request) -> Response:
        """
        :return: 201 with the newly created profile; 403 if the caller lacks the required role
            flag; 400 if a profile already exists (one per user - see get_object).
        """
        if not self.role_check(request.user):
            return Response({"detail": self.role_error}, status=status.HTTP_403_FORBIDDEN)
        if self.get_object() is not None:
            return Response(
                {"detail": _("A profile of this type already exists for your account.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(user=request.user)
        except IntegrityError:
            # Race: two near-simultaneous POSTs both pass the get_object() check above before
            # either commits - the OneToOneField primary key catches the second one here.
            return Response(
                {"detail": _("A profile of this type already exists for your account.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request: Request) -> Response:
        """:return: 200 with the updated profile, or 404 if the caller hasn't created one yet."""
        profile = self.get_object()
        if profile is None:
            raise NotFound()
        serializer = self.serializer_class(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class OwnerProfileView(SelfProfileView):
    """Self-service create/view/update of the caller's own OwnerProfile."""

    serializer_class = OwnerProfileSerializer
    related_name = "owner_profile"
    role_error = _("Only accounts with owner status may create an owner profile.")

    @staticmethod
    def role_check(user: User) -> bool:
        return user.is_owner


class AgentProfileView(SelfProfileView):
    """Self-service create/view/update of the caller's own AgentProfile."""

    serializer_class = AgentProfileSerializer
    related_name = "agent_profile"
    role_error = _("Only accounts with agent status may create an agent profile.")

    @staticmethod
    def role_check(user: User) -> bool:
        return user.is_agent


class TenantProfileView(SelfProfileView):
    """Self-service create/view/update of the caller's own TenantProfile - no role flag required."""

    serializer_class = TenantProfileSerializer
    related_name = "tenant_profile"


class VerifyOwnerProfileView(APIView):
    """
    Moderator-only endpoint confirming an owner's submitted documents (OwnerProfile.
    verification_document) are genuine. Symmetric to PropertyViewSet.moderate() - the user
    proposes (self-service creation above), a moderator confirms; there is no way for a user to
    self-certify.
    """

    permission_classes = [IsModerator]
    serializer_class = OwnerProfileSerializer

    def post(self, request: Request, user_id: int) -> Response:
        """
        :param user_id: the pk of the User whose OwnerProfile is being verified.
        :return: 200 with the now-verified profile, 404 if no OwnerProfile exists for that user.
        """
        profile = get_object_or_404(OwnerProfile, user_id=user_id)
        profile.is_verified = True
        profile.verified_at = timezone.now()
        profile.save(update_fields=["is_verified", "verified_at"])
        return Response(OwnerProfileSerializer(profile).data)


class CertifyAgentProfileView(APIView):
    """
    Moderator-only endpoint certifying an agent (AgentProfile.is_certified). Property.clean()
    requires this before a listing can be created with listed_as=agent - this is the only way
    that flag is ever set to True.
    """

    permission_classes = [IsModerator]
    serializer_class = AgentProfileSerializer

    def post(self, request: Request, user_id: int) -> Response:
        """
        :param user_id: the pk of the User whose AgentProfile is being certified.
        :return: 200 with the now-certified profile, 404 if no AgentProfile exists for that user.
        """
        profile = get_object_or_404(AgentProfile, user_id=user_id)
        profile.is_certified = True
        profile.save(update_fields=["is_certified"])
        return Response(AgentProfileSerializer(profile).data)
