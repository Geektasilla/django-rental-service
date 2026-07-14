"""
Shared test-data builders for integration tests across apps.

Kept deliberately minimal (not a full factory_boy setup) - just enough to remove the boilerplate
of "create a user with an ACTIVE role profile" and "create a valid Property", which every
integration test touching bookings/listings otherwise has to repeat.
"""
import itertools

from common.models import ProfileStatusChoices
from listings.models import Category, Property
from users.models import User
from users.models.agent import AgentProfile
from users.models.owner import OwnerProfile
from users.models.tenant import TenantProfile

_phone_counter = itertools.count(1)


def _unique_phone() -> str:
    """:return: a fresh, valid, unique phone number for each call within a test run."""
    return f"+49170{next(_phone_counter):07d}"


def make_tenant(email: str = "tenant@example.com", password: str = "TestPass123!") -> User:
    """:return: a User with is_owner/is_agent False and an ACTIVE TenantProfile."""
    user = User.objects.create_user(email=email, password=password, phone=_unique_phone())
    TenantProfile.objects.create(user=user, passport_data="P1234567", status=ProfileStatusChoices.ACTIVE)
    return user


def make_owner(email: str = "owner@example.com", password: str = "TestPass123!", verified: bool = True) -> User:
    """
    :param verified: OwnerProfile.is_verified - defaults True since most tests just need a
        working owner, not to exercise verification itself (see OwnerIsVerifiedToConfirm). Pass
        False explicitly for tests of the unverified-owner-can't-confirm rule.
    :return: a User with is_owner=True and an ACTIVE OwnerProfile.
    """
    user = User.objects.create_user(email=email, password=password, phone=_unique_phone(), is_owner=True)
    OwnerProfile.objects.create(
        user=user, tax_id="DE123456789", status=ProfileStatusChoices.ACTIVE, is_verified=verified
    )
    return user


def make_certified_agent(email: str = "agent@example.com", password: str = "TestPass123!") -> User:
    """:return: a User with is_agent=True and an ACTIVE, certified AgentProfile."""
    user = User.objects.create_user(email=email, password=password, phone=_unique_phone(), is_agent=True)
    AgentProfile.objects.create(
        user=user,
        company_name="Test Agency",
        license_number="LIC-001",
        is_certified=True,
        status=ProfileStatusChoices.ACTIVE,
    )
    return user


def make_property(owner: User, **overrides) -> Property:
    """
    :param owner: the listing's owner (must have an active owner or certified agent profile).
    :param overrides: any Property field to override (e.g. rent_type, price_per_day).
    :return: a saved, valid Property with sane DAILY-rental defaults.
    """
    category, _ = Category.objects.get_or_create(name="Apartment")
    fields = {
        "owner": owner,
        "category": category,
        "title": "Test flat",
        "description": "A place to stay.",
        "rent_type": Property.RentTypeChoices.DAILY,
        "price_per_day": "50.00",
        "rooms_count": 2,
        "listed_as": Property.ListedAsChoices.OWNER,
    }
    fields.update(overrides)
    return Property.objects.create(**fields)
