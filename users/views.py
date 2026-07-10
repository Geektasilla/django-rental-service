from rest_framework import status
from rest_framework.generics import CreateAPIView, GenericAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from users.serializers import LogoutSerializer, RegisterSerializer, UserProfileSerializer


class RegisterView(CreateAPIView):
    """Public self-registration endpoint (AllowAny)."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


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
                {"detail": "Invalid or already blacklisted refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


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
