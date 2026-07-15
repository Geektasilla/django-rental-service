from analytics.models import PropertyView, SearchHistory
from notifications.models import Notification
from users.models import User
from users.tokens import revoke_all_sessions


def anonymize_user(user: User) -> None:
    """
    Fulfil a GDPR Art. 17 erasure request without violating German retention law.

    Booking.tenant and Ticket.user are on_delete=PROTECT (Booking/Ticket rows must be retained per
    HGB/AO tax-record rules), so User.delete() is not possible for any user with booking/ticket
    history. Instead, personal fields are scrubbed on the User and their role profiles while the
    row itself (and anything referencing it via PROTECT) stays in place - the standard pattern
    used by German rental/booking platforms for this exact conflict.

    Data with no legal retention requirement (search history, property views, notifications) is
    deleted outright rather than anonymized, since there's nothing worth keeping.

    :param user: the account to anonymize. Already-anonymized accounts are left as-is (idempotent
        on email, checked by the caller via the "anonymized.local" suffix, not enforced here).
    """
    user.email = f"deleted-user-{user.pk}@anonymized.local"
    user.first_name = ""
    user.last_name = ""
    user.phone = f"+1{user.pk:013d}"
    user.gender = User.GenderChoices.UNSPECIFIED
    user.is_active = False
    user.set_unusable_password()
    user.save()

    if hasattr(user, "owner_profile"):
        profile = user.owner_profile
        profile.tax_id = ""
        profile.bio = ""
        profile.languages = ""
        profile.verification_document.delete(save=False)
        profile.verification_document = None
        profile.save()

    if hasattr(user, "agent_profile"):
        profile = user.agent_profile
        profile.license_number = ""
        profile.bio = ""
        profile.website = None
        profile.save()

    if hasattr(user, "tenant_profile"):
        profile = user.tenant_profile
        profile.passport_data = ""
        profile.save()

    SearchHistory.objects.filter(user=user).delete()
    PropertyView.objects.filter(user=user).delete()
    Notification.objects.filter(user=user).delete()

    revoke_all_sessions(user)
