import random
import uuid
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker
from PIL import Image

from analytics.models import PropertyView, SearchHistory
from bookings.models import Booking, BookingStatusChoices
from common.utils import top_up
from listings.models import (
    Address,
    Amenity,
    Category,
    PostalCode,
    Property,
    PropertyImage,
    PropertyLocation,
)
from reviews.models import Review
from users.models import AgentProfile, OwnerProfile, TenantProfile, User

SEED_PASSWORD = "TestPass123!"
SEED_EMAIL_DOMAIN = "example.com"
USER_COUNT = 50
PROPERTY_COUNT = 80
SEARCH_HISTORY_COUNT = 200
# Safety valve for the retry-until-target while loops: a handful of retries covers a rare
# random collision, but if every attempt keeps failing (a real bug, not bad luck), stop
# instead of looping forever.
MAX_ATTEMPTS_PER_TARGET = 10

CATEGORY_NAMES = ["Apartment", "House", "Studio", "Room"]
AMENITY_NAMES = [
    "Wi-Fi", "Parking", "Washer", "Dishwasher", "Balcony",
    "Elevator", "Pet Friendly", "Air Conditioning",
]

# Real German postal codes, spread across several cities/states.
GERMAN_POSTAL_CODES = [
    ("10115", "Berlin", "Berlin"),
    ("10117", "Berlin", "Berlin"),
    ("10119", "Berlin", "Berlin"),
    ("10178", "Berlin", "Berlin"),
    ("10243", "Berlin", "Berlin"),
    ("80331", "München", "Bayern"),
    ("80333", "München", "Bayern"),
    ("80469", "München", "Bayern"),
    ("50667", "Köln", "Nordrhein-Westfalen"),
    ("50672", "Köln", "Nordrhein-Westfalen"),
    ("20095", "Hamburg", "Hamburg"),
    ("20144", "Hamburg", "Hamburg"),
    ("60311", "Frankfurt am Main", "Hessen"),
    ("70173", "Stuttgart", "Baden-Württemberg"),
    ("04109", "Leipzig", "Sachsen"),
]

SEARCH_KEYWORDS = [
    "apartment Berlin", "cheap studio Munich", "WG Köln", "Wohnung Frankfurt",
    "2 bedroom house Hamburg", "pet friendly apartment", "furnished room Leipzig",
    "long term rental Stuttgart", "studio near center", "parking included",
]


class Command(BaseCommand):
    """
    Fill the database with realistic fake data for local development/demo purposes.

    Safe to re-run after a failure: users and properties are checkpointed (each is created
    in its own small transaction, so a crash only loses the one record being written, not
    prior progress), and re-running tops up up to USER_COUNT/PROPERTY_COUNT instead of
    starting over or duplicating what's already there.
    """

    help = "Fill the database with test data (users, listings, bookings, reviews, analytics)."

    def handle(self, *args, **kwargs) -> None:
        if not settings.DEBUG:
            raise CommandError("seed_data can only run with DEBUG=True (refusing to seed a production database).")

        fake = Faker("de_DE")
        today = timezone.now().date()

        self.stdout.write("Creating categories, amenities and postal codes...")
        categories, amenities, postal_codes = self._create_reference_data()

        self.stdout.write(f"Creating users (target: {USER_COUNT})...")
        users, landlords, tenants = self._create_users(fake)

        self.stdout.write(f"Creating properties (target: {PROPERTY_COUNT})...")
        properties = self._create_properties(fake, landlords, categories, amenities, postal_codes)

        self.stdout.write("Creating bookings...")
        past_paid_bookings = self._create_bookings(fake, tenants, properties, today)

        self.stdout.write("Creating reviews...")
        self._create_reviews(fake, past_paid_bookings, today)

        self.stdout.write("Creating search history and property views...")
        self._create_search_history(users)
        self._create_property_views(fake, users, properties)

        self.stdout.write(self.style.SUCCESS("Database filled successfully."))

    def _create_reference_data(self) -> tuple[list[Category], list[Amenity], list[PostalCode]]:
        with transaction.atomic():
            categories = [Category.objects.get_or_create(name=name)[0] for name in CATEGORY_NAMES]
            amenities = [Amenity.objects.get_or_create(name=name)[0] for name in AMENITY_NAMES]
            postal_codes = [
                PostalCode.objects.get_or_create(code=code, defaults={"city": city, "state": state})[0]
                for code, city, state in GERMAN_POSTAL_CODES
            ]
        return categories, amenities, postal_codes

    def _create_users(self, fake: Faker) -> tuple[list[User], list[User], list[User]]:
        """
        Top up existing seed users to USER_COUNT instead of always creating a fresh batch,
        so a previous partial/failed run doesn't leave duplicated or orphaned data behind.

        :return: (all_users, landlords - is_owner or is_agent, tenants - has a TenantProfile).
        """
        users: list[User] = list(User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}"))
        tenant_user_ids = set(
            TenantProfile.objects.filter(user__in=users).values_list("user_id", flat=True)
        )
        certified_agent_ids = set(
            AgentProfile.objects.filter(user__in=users, is_certified=True).values_list("user_id", flat=True)
        )
        # Only a user with owner status, or a *certified* agent, may list a property at all
        # (see Property.clean() - an uncertified agent with no owner status can list nothing).
        landlords = [u for u in users if u.is_owner or u.pk in certified_agent_ids]
        tenants = [u for u in users if u.pk in tenant_user_ids]

        def create_one_user() -> User:
            is_owner = random.random() < 0.3
            is_agent = random.random() < 0.15
            is_tenant = random.random() < 0.7
            is_certified_agent = is_agent and random.random() < 0.7

            with transaction.atomic():
                user = User.objects.create_user(
                    email=f"{uuid.uuid4().hex[:8]}@{SEED_EMAIL_DOMAIN}",
                    password=SEED_PASSWORD,
                    phone=f"+49{random.randint(100_000_000, 999_999_999)}",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    gender=random.choice(User.GenderChoices.values),
                    is_owner=is_owner,
                    is_agent=is_agent,
                )
                if is_owner:
                    OwnerProfile.objects.create(
                        user=user,
                        tax_id=fake.numerify("DE#########"),
                        bio=fake.text(max_nb_chars=200),
                        is_company=random.random() < 0.3,
                        company_name=fake.company() if random.random() < 0.3 else "",
                        languages="German, English",
                        is_verified=True,
                        verified_at=timezone.now(),
                    )
                if is_agent:
                    AgentProfile.objects.create(
                        user=user,
                        company_name=fake.company(),
                        license_number=fake.numerify("LIC-######"),
                        is_certified=is_certified_agent,
                        bio=fake.text(max_nb_chars=200),
                    )
                if is_tenant:
                    TenantProfile.objects.create(user=user, passport_data=fake.numerify("P#########"))

            if is_owner or is_certified_agent:
                landlords.append(user)
            if is_tenant:
                tenants.append(user)
            return user

        top_up(
            users,
            USER_COUNT,
            create_one_user,
            max_attempts_per_target=MAX_ATTEMPTS_PER_TARGET,
            label="users",
            on_error=lambda exc: self.stderr.write(self.style.WARNING(f"Skipping one user due to error: {exc}")),
        )

        return users, landlords, tenants

    def _create_properties(
        self,
        fake: Faker,
        landlords: list[User],
        categories: list[Category],
        amenities: list[Amenity],
        postal_codes: list[PostalCode],
    ) -> list[Property]:
        """Top up existing seed properties to PROPERTY_COUNT (same checkpointing idea as users)."""
        properties: list[Property] = list(
            Property.objects.filter(owner__email__endswith=f"@{SEED_EMAIL_DOMAIN}")
        )

        def create_one_property() -> Property:
            owner = random.choice(landlords)
            can_list_as_owner = owner.is_owner
            agent_profile = getattr(owner, "agent_profile", None)
            can_list_as_agent = bool(agent_profile and agent_profile.is_certified)

            if can_list_as_owner and can_list_as_agent:
                listed_as = random.choice([Property.ListedAsChoices.OWNER, Property.ListedAsChoices.AGENT])
            elif can_list_as_agent:
                listed_as = Property.ListedAsChoices.AGENT
            else:
                listed_as = Property.ListedAsChoices.OWNER

            poa_document = (
                self._fake_document_file(f"seed_poa_{uuid.uuid4().hex[:8]}.txt")
                if listed_as == Property.ListedAsChoices.AGENT
                else None
            )

            rent_type = random.choice(Property.RentTypeChoices.values)
            is_daily = rent_type == Property.RentTypeChoices.DAILY

            with transaction.atomic():
                postal_code = random.choice(postal_codes)
                address, _ = Address.objects.get_or_create(
                    postal_code=postal_code,
                    street=fake.street_name(),
                    house_number=str(random.randint(1, 150)),
                )

                property_ = Property.objects.create(
                    owner=owner,
                    title=fake.sentence(nb_words=5).rstrip("."),
                    description=fake.paragraph(nb_sentences=5),
                    category=random.choice(categories),
                    rent_type=rent_type,
                    price_per_day=Decimal(random.randrange(20, 300)) if is_daily else None,
                    price_per_month=None if is_daily else Decimal(random.randrange(400, 3000)),
                    rooms_count=random.randint(1, 6),
                    is_active=True,
                    listed_as=listed_as,
                    power_of_attorney_document=poa_document,
                )
                # The moderation signal only ever rejects, never approves - force-approve
                # seeded listings via .update() so it doesn't retrigger the post_save signal.
                Property.objects.filter(pk=property_.pk).update(
                    moderation_status=Property.ModerationStatusChoices.APPROVED,
                )
                property_.moderation_status = Property.ModerationStatusChoices.APPROVED

                property_.amenities.set(random.sample(amenities, k=random.randint(1, len(amenities))))

                PropertyLocation.objects.create(
                    property=property_,
                    address=address,
                    apartment_number=str(random.randint(1, 40)) if random.random() < 0.6 else "",
                    floor_info=f"{random.randint(1, 6)}. Stock" if random.random() < 0.6 else "",
                )

            for i in range(random.randint(2, 5)):
                try:
                    PropertyImage.objects.create(
                        property=property_,
                        image=self._fake_image_file(f"seed_{property_.pk}_{i}.jpg"),
                    )
                except OSError as exc:
                    self.stderr.write(self.style.WARNING(f"Skipping image for property {property_.pk}: {exc}"))

            return property_

        top_up(
            properties,
            PROPERTY_COUNT,
            create_one_property,
            max_attempts_per_target=MAX_ATTEMPTS_PER_TARGET,
            label="properties",
            on_error=lambda exc: self.stderr.write(self.style.WARNING(f"Skipping one property due to error: {exc}")),
        )

        return properties

    def _fake_image_file(self, name: str) -> ContentFile:
        """Generate a small solid-color JPEG in memory, avoiding network calls for seed images."""
        buffer = BytesIO()
        color = tuple(random.randint(0, 255) for _ in range(3))
        Image.new("RGB", (600, 400), color=color).save(buffer, format="JPEG")
        return ContentFile(buffer.getvalue(), name=name)

    def _fake_document_file(self, name: str) -> ContentFile:
        """Generate a plaintext stand-in for a power of attorney document."""
        return ContentFile(b"Fake power of attorney document generated for seed data.", name=name)

    def _create_bookings(
        self,
        fake: Faker,
        tenants: list[User],
        properties: list[Property],
        today,
    ) -> list[Booking]:
        past_paid_bookings: list[Booking] = []

        for property_ in properties:
            if random.random() >= 0.7:
                continue

            cursor = today - timedelta(days=random.randint(180, 365))
            for _ in range(random.randint(1, 4)):
                is_past = cursor < today
                duration = (
                    random.randint(2, 14)
                    if property_.rent_type == Property.RentTypeChoices.DAILY
                    else random.randint(90, 365)
                )
                start_date = cursor
                end_date = start_date + timedelta(days=duration)
                status = (
                    BookingStatusChoices.PAID
                    if is_past
                    else random.choice([BookingStatusChoices.PENDING, BookingStatusChoices.BOOKED])
                )

                try:
                    with transaction.atomic():
                        booking = Booking.objects.create(
                            property=property_,
                            tenant=random.choice(tenants),
                            start_date=start_date,
                            end_date=end_date,
                            status=status,
                        )
                except Exception as exc:
                    self.stderr.write(
                        self.style.WARNING(f"Skipping a booking for property {property_.pk}: {exc}")
                    )
                    cursor = end_date + timedelta(days=random.randint(1, 10))
                    continue

                if status == BookingStatusChoices.PAID:
                    past_paid_bookings.append(booking)
                cursor = end_date + timedelta(days=random.randint(1, 10))

        return past_paid_bookings

    def _create_reviews(self, fake: Faker, past_paid_bookings: list[Booking], today) -> None:
        for booking in past_paid_bookings:
            if (today - booking.end_date).days > 90:
                continue
            if random.random() >= 0.6:
                continue
            try:
                with transaction.atomic():
                    Review.objects.create(
                        booking=booking,
                        rating=random.randint(1, 5),
                        comment=fake.paragraph(nb_sentences=3),
                    )
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f"Skipping a review for booking {booking.pk}: {exc}"))

    def _create_search_history(self, users: list[User]) -> None:
        with transaction.atomic():
            for _ in range(SEARCH_HISTORY_COUNT):
                SearchHistory.objects.create(
                    user=random.choice(users) if random.random() < 0.6 else None,
                    search_query=random.choice(SEARCH_KEYWORDS),
                )

    def _create_property_views(self, fake: Faker, users: list[User], properties: list[Property]) -> None:
        popular_properties = set(random.sample(properties, k=4))

        with transaction.atomic():
            for property_ in properties:
                view_count = random.randint(20, 60) if property_ in popular_properties else random.randint(0, 10)
                for _ in range(view_count):
                    is_authenticated = random.random() < 0.6
                    PropertyView.objects.create(
                        property=property_,
                        user=random.choice(users) if is_authenticated else None,
                        ip_address=None if is_authenticated else fake.ipv4(),
                    )
