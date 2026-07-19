from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

phone_validator = RegexValidator(
    regex=r"^\+?[1-9]\d{7,14}$",
    message=_(
        "Enter a valid phone number in international format, e.g. +491701234567."
    ),
)



class UserManager(BaseUserManager):
    """Manager for the custom User model, keyed on email instead of username."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields) -> "User":
        """
        Instantiate, hash the password for, and save a new user.

        :param email: user's email address, used as the login identifier.
        :param password: raw password to hash and store; left unusable if None.
        :param extra_fields: additional model field values (e.g. is_staff, is_superuser).
        :return: the newly created User instance.
        """
        if not email:
            raise ValueError(_("The email address must be set."))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(
        self, email: str, password: str | None = None, **extra_fields
    ) -> "User":
        """
        Create and save a regular (non-staff, non-superuser) user.

        :param email: user's email address, used as the login identifier.
        :param password: raw password to hash and store; left unusable if None.
        :param extra_fields: additional model field values.
        :return: the newly created User instance.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields
    ) -> "User":
        """
        Create and save a superuser with is_staff and is_superuser both True.

        :param email: user's email address, used as the login identifier.
        :param password: raw password to hash and store; left unusable if None.
        :param extra_fields: additional model field values.
        :return: the newly created User instance.
        :raises ValueError: if is_staff or is_superuser is explicitly overridden to False.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model authenticated by email; role access is granted via boolean flags."""

    username = None
    email = models.EmailField(_("email address"), unique=True)
    phone = models.CharField(
        _("phone number"),
        max_length=20,
        unique=True,
        validators=[phone_validator],
    )
    is_owner = models.BooleanField(
        _("owner status"),
        default=False,
        help_text=_("Grants access to landlord (property owner) features."),
    )
    is_agent = models.BooleanField(
        _("agent status"),
        default=False,
        help_text=_("Grants access to real estate agent features."),
    )
    is_support = models.BooleanField(
        _("support status"),
        default=False,
        help_text=_(
            "Grants access to support ticket features. Settable only via admin, never via a public serializer."
        ),
    )
    is_moderator = models.BooleanField(
        _("moderator status"),
        default=False,
        help_text=_(
            "Grants access to listing moderation features. Settable only via admin, never via a public serializer."
        ),
    )
    is_email_verified = models.BooleanField(
        _("email verified"),
        default=False,
        help_text=_(
            "Set once the user confirms their email via the verification link. Informational only for now."
        ),
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone"]

    class GenderChoices(models.TextChoices):
        """Self-reported gender, shown on the user's profile."""

        MALE = "male", _("Male")
        FEMALE = "female", _("Female")
        OTHER = "other", _("Other / Non-binary")
        UNSPECIFIED = "unspecified", _("Prefer not to say")  # Default

    gender = models.CharField(
        _("gender"),
        max_length=20,
        choices=GenderChoices.choices,
        default=GenderChoices.UNSPECIFIED,
    )

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints = [
            # Hardcoded, not GenderChoices.values: nested TextChoices isn't visible from Meta.
            models.CheckConstraint(
                condition=models.Q(
                    gender__in=["male", "female", "other", "unspecified"]
                ),
                name="user_gender_valid",
            ),
        ]

    def __str__(self) -> str:
        """
        :return: the user's email address.
        """
        return self.email

    def save(self, *args, **kwargs) -> None:
        """
        This makes sure all fields are checked (like the phone number)
        every time we save this user to the database.
        It guarantees the data is always correct,
        no matter if it's saved from a form, an API, or directly from code.
        """
        self.full_clean()
        super().save(*args, **kwargs)
