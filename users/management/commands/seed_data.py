import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

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
from support.models import Message, Ticket
from users.models import AgentProfile, OwnerProfile, TenantProfile, User

USER_COUNT = 150
PROPERTY_COUNT = 100
CERTIFIED_AGENT_LANDLORD_WEIGHT = 6
PRIVATE_OWNER_LANDLORD_WEIGHT = 1
SEARCH_HISTORY_COUNT = 200
TICKET_COUNT = 40
MAX_ATTEMPTS_PER_TARGET = 10
MAX_PAST_BOOKING_DAYS = 365

PROPERTY_PHOTOS_DIR = settings.MEDIA_ROOT / "property_photos"

CATEGORY_NAMES = ["Apartment", "House", "Studio", "Room"]
AMENITY_NAMES = [
    "Wi-Fi", "Parking", "Washer", "Dishwasher", "Balcony",
    "Elevator", "Pet Friendly", "Air Conditioning",
]

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

TITLE_ADJECTIVE_STEMS = [
    "Gemütlich", "Hell", "Modern", "Zentral", "Ruhig",
    "Charmant", "Stilvoll", "Sonnig", "Geräumig", "Renoviert",
]
CATEGORY_NOUNS_DE = {
    "Apartment": "Wohnung",
    "House": "Haus",
    "Studio": "Studio-Wohnung",
    "Room": "Zimmer",
}
NEUTER_NOUNS_DE = {"Haus", "Zimmer"}

DESCRIPTION_SENTENCES_GENERAL = [
    "Die Wohnung liegt zentral und ist gut an öffentliche Verkehrsmittel angebunden.",
    "In der Nähe befinden sich Supermärkte, Restaurants und Parks.",
    "Die Räume sind hell und modern eingerichtet.",
    "Haustiere sind nach Absprache willkommen.",
    "Ein Balkon und ausreichend Stauraum runden das Angebot ab.",
    "Die Küche ist voll ausgestattet und einladend.",
]
DESCRIPTION_SENTENCES_DAILY = [
    "Perfekt für einen Kurzurlaub oder eine Geschäftsreise.",
    "Kurzfristige Buchungen sind jederzeit möglich.",
]
DESCRIPTION_SENTENCES_LONG_TERM = [
    "Langfristige Miete ist ab sofort möglich.",
    "Ideal für alle, die auf der Suche nach einem dauerhaften Zuhause sind.",
]

REVIEW_COMMENTS_POSITIVE = [
    "Ein toller Aufenthalt, alles war sauber und wie beschrieben.",
    "Der Vermieter war sehr freundlich und hat schnell geantwortet.",
    "Wir kommen auf jeden Fall wieder, absolute Empfehlung!",
    "Die Lage war perfekt und die Wohnung genau wie auf den Fotos.",
]
REVIEW_COMMENTS_NEUTRAL = [
    "Insgesamt in Ordnung, ein paar Kleinigkeiten könnten verbessert werden.",
    "Die Wohnung war okay, aber nicht ganz so groß wie erwartet.",
    "Guter Aufenthalt, die Kommunikation hätte aber schneller sein können.",
]
REVIEW_COMMENTS_NEGATIVE = [
    "Leider nicht ganz wie beschrieben, wir waren etwas enttäuscht.",
    "Die Wohnung war bei unserer Ankunft nicht besonders sauber.",
    "Der Kontakt zum Vermieter war leider schwierig.",
]

OWNER_BIO_SENTENCES = [
    "Vermietet seit mehreren Jahren zuverlässig Wohnungen und Häuser in der Region.",
    "Legt großen Wert auf eine gepflegte Immobilie und einen freundlichen Kontakt zu den Mietern.",
    "Bietet flexible Besichtigungstermine und eine schnelle, unkomplizierte Kommunikation.",
    "Achtet auf eine faire und transparente Vermietung.",
]
AGENT_BIO_SENTENCES = [
    "Spezialisiert auf die Vermittlung von Wohnungen und Häusern im Stadtgebiet.",
    "Verfügt über mehrjährige Erfahrung in der Immobilienvermittlung.",
    "Begleitet Mieter und Vermieter kompetent durch den gesamten Vermietungsprozess.",
    "Bietet eine persönliche Beratung und schnelle Terminvereinbarung.",
]

TICKET_SUBJECTS = [
    "Frage zur Buchung", "Problem mit der Zahlung", "Wohnung nicht wie beschrieben",
    "Stornierung einer Buchung", "Frage zum Vermieter", "Technisches Problem mit dem Konto",
    "Frage zur Rechnung", "Verifizierung des Kontos",
]
TICKET_OPENING_MESSAGES = [
    "Ich habe eine Frage zu meiner aktuellen Buchung und wüsste gerne mehr Details.",
    "Bei der Zahlung ist ein Fehler aufgetreten, könnten Sie das bitte prüfen?",
    "Die Wohnung entsprach leider nicht der Beschreibung im Inserat.",
    "Ich möchte meine Buchung stornieren und frage nach den Bedingungen.",
    "Mein Konto lässt sich nicht wie erwartet verwenden, können Sie helfen?",
]
TICKET_REPLY_MESSAGES = [
    "Vielen Dank für Ihre Nachricht, wir kümmern uns umgehend darum.",
    "Könnten Sie uns bitte weitere Details zu Ihrem Anliegen mitteilen?",
    "Das Problem wurde geprüft und sollte nun behoben sein.",
    "Wir haben Ihre Anfrage an das zuständige Team weitergeleitet.",
]


def build_property_title(category_name: str, rooms_count: int, city: str) -> str:
    """
    :param category_name: Category.name of the listing (e.g. "Apartment", "Room").
    :param rooms_count: number of rooms.
    :param city: the listing's city (PostalCode.city).
    :return: a realistic German listing title, e.g. "Gemütliche 3-Zimmer-Wohnung in Berlin".
    """
    noun = CATEGORY_NOUNS_DE.get(category_name, "Immobilie")
    stem = random.choice(TITLE_ADJECTIVE_STEMS)
    adjective = f"{stem}es" if noun in NEUTER_NOUNS_DE else f"{stem}e"
    if noun == "Zimmer":
        return f"{adjective} {noun} in {city}"
    return f"{adjective} {rooms_count}-Zimmer-{noun} in {city}"


def build_property_description(rent_type: str, rooms_count: int, city: str) -> str:
    """
    :param rent_type: Property.RentTypeChoices value ("daily" or "long_term").
    :param rooms_count: number of rooms.
    :param city: the listing's city (PostalCode.city).
    :return: a short, grammatically correct German description paragraph.
    """
    intro = f"Diese Immobilie bietet {rooms_count} Zimmer in {city}."
    rent_pool = DESCRIPTION_SENTENCES_DAILY if rent_type == Property.RentTypeChoices.DAILY else DESCRIPTION_SENTENCES_LONG_TERM
    sentences = random.sample(DESCRIPTION_SENTENCES_GENERAL, k=random.randint(2, 3))
    sentences.append(random.choice(rent_pool))
    random.shuffle(sentences)
    return " ".join([intro, *sentences])


def build_review_comment(rating: int) -> str:
    """
    :param rating: the review's star rating (1-5).
    :return: a realistic German comment whose tone matches the rating.
    """
    if rating >= 4:
        pool = REVIEW_COMMENTS_POSITIVE
    elif rating == 3:
        pool = REVIEW_COMMENTS_NEUTRAL
    else:
        pool = REVIEW_COMMENTS_NEGATIVE
    return random.choice(pool)


def build_owner_bio() -> str:
    """:return: a short, grammatically correct German bio for a private landlord."""
    return " ".join(random.sample(OWNER_BIO_SENTENCES, k=random.randint(1, 2)))


def build_agent_bio() -> str:
    """:return: a short, grammatically correct German bio for a real estate agent."""
    return " ".join(random.sample(AGENT_BIO_SENTENCES, k=random.randint(1, 2)))


class Command(BaseCommand):
    """
    Fill the database with realistic fake data for local development/demo purposes.

    Safe to re-run after a failure: users and properties are checkpointed (each is created
    in its own small transaction, so a crash only loses the one record being written, not
    prior progress), and re-running tops up  to USER_COUNT/PROPERTY_COUNT instead of
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

        self.stdout.write(f"Creating support tickets (target: {TICKET_COUNT})...")
        self._create_support_tickets(users)

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
        users: list[User] = list(User.objects.filter(email__endswith=f"@{settings.SEED_EMAIL_DOMAIN}"))
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
            # Small, fixed pool of support agents - not tied to any profile (unlike owner/agent/
            # tenant, is_support is a plain flag), just enough that _create_support_tickets() has
            # someone to auto-assign to. Set directly here, same as is_owner/is_agent below: this
            # is a trusted management command, not the public serializer the model docstring warns
            # against (see users/models/base_user.py).
            is_support = random.random() < 0.08

            with transaction.atomic():
                user = User.objects.create_user(
                    email=f"{uuid.uuid4().hex[:8]}@{settings.SEED_EMAIL_DOMAIN}",
                    password=settings.SEED_PASSWORD,
                    phone=f"+49{random.randint(100_000_000, 999_999_999)}",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    gender=random.choice(User.GenderChoices.values),
                    is_owner=is_owner,
                    is_agent=is_agent,
                    is_support=is_support,
                )
                if is_owner:
                    OwnerProfile.objects.create(
                        user=user,
                        tax_id=fake.numerify("DE#########"),
                        bio=build_owner_bio(),
                        is_company=random.random() < 0.3,
                        company_name=fake.company() if random.random() < 0.3 else "",
                        languages="German, English",
                        is_verified=True,
                        verified_at=timezone.now(),
                        verification_document=self._fake_document_file(
                            f"seed_verification_{uuid.uuid4().hex[:8]}.txt"
                        ),
                    )
                if is_agent:
                    AgentProfile.objects.create(
                        user=user,
                        company_name=fake.company(),
                        license_number=fake.numerify("LIC-######"),
                        is_certified=is_certified_agent,
                        bio=build_agent_bio(),
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
            Property.objects.filter(owner__email__endswith=f"@{settings.SEED_EMAIL_DOMAIN}")
        )
        self._property_photo_pool = self._load_property_photo_pool()

        def _is_certified_agent(user: User) -> bool:
            agent_profile = getattr(user, "agent_profile", None)
            return bool(agent_profile and agent_profile.is_certified)

        landlord_weights = [
            CERTIFIED_AGENT_LANDLORD_WEIGHT if _is_certified_agent(u) else PRIVATE_OWNER_LANDLORD_WEIGHT
            for u in landlords
        ]

        def create_one_property() -> Property:
            owner = random.choices(landlords, weights=landlord_weights, k=1)[0]
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
            category = random.choice(categories)
            rooms_count = random.randint(1, 6)

            with transaction.atomic():
                postal_code = random.choice(postal_codes)
                address, _ = Address.objects.get_or_create(
                    postal_code=postal_code,
                    street=fake.street_name(),
                    house_number=str(random.randint(1, 150)),
                )

                property_ = Property.objects.create(
                    owner=owner,
                    title=build_property_title(category.name, rooms_count, postal_code.city),
                    description=build_property_description(rent_type, rooms_count, postal_code.city),
                    category=category,
                    rent_type=rent_type,
                    price_per_day=Decimal(random.randrange(20, 300)) if is_daily else None,
                    price_per_month=None if is_daily else Decimal(random.randrange(400, 3000)),
                    rooms_count=rooms_count,
                    is_active=True,
                    listed_as=listed_as,
                    power_of_attorney_document=poa_document,
                )
                # The moderation signal only ever rejects, never approves - force-approve
                # seeded listings via .update() so it doesn't retrigger the post_save signal.
                # Backdate created_at (auto_now_add otherwise forces it to "now") well before the
                # furthest-back simulated booking (_create_bookings), so a listing never appears
                # to have been booked before it existed.
                backdated_created_at = timezone.now() - timedelta(
                    days=random.randint(MAX_PAST_BOOKING_DAYS + 5, MAX_PAST_BOOKING_DAYS + 135)
                )
                Property.objects.filter(pk=property_.pk).update(
                    moderation_status=Property.ModerationStatusChoices.APPROVED,
                    created_at=backdated_created_at,
                )
                property_.moderation_status = Property.ModerationStatusChoices.APPROVED
                property_.created_at = backdated_created_at

                property_.amenities.set(random.sample(amenities, k=random.randint(1, len(amenities))))

                PropertyLocation.objects.create(
                    property=property_,
                    address=address,
                    apartment_number=str(random.randint(1, 40)) if random.random() < 0.6 else "",
                    floor_info=f"{random.randint(1, 6)}. Stock" if random.random() < 0.6 else "",
                )

            folder = property_.category.name.lower()
            photos = self._property_photo_pool.get(folder, [])
            for _ in range(random.randint(2, 5)):
                if not photos:
                    break
                PropertyImage.objects.create(
                    property=property_,
                    image=f"property_photos/{folder}/{random.choice(photos)}",
                )

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

    def _load_property_photo_pool(self) -> dict[str, list[str]]:
        """Filenames under media/property_photos/<category>/, keyed by lowercased category name."""
        pool = {}
        for folder in CATEGORY_NAMES:
            folder = folder.lower()
            category_dir = PROPERTY_PHOTOS_DIR / folder
            if category_dir.is_dir():
                pool[folder] = [f.name for f in category_dir.iterdir() if f.is_file()]
        return pool

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

            cursor = today - timedelta(days=random.randint(180, MAX_PAST_BOOKING_DAYS))
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
                    rating = random.randint(1, 5)
                    Review.objects.create(
                        booking=booking,
                        rating=rating,
                        comment=build_review_comment(rating),
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

    def _create_support_tickets(self, users: list[User]) -> None:
        """
        Give the support app some data to demo too - an always-empty support inbox isn't useful to
        show. Unlike users/properties, a ticket has no natural "top up to N" business meaning, so
        this is a plain fixed-count loop with a per-item try/except (same pattern already used for
        _create_bookings/_create_reviews) rather than common.utils.top_up() - a partial re-run
        just adds a few more tickets, which is harmless.

        Mirrors TicketViewSet.perform_create()'s auto-assignment idea (fewest open tickets per
        agent) loosely: assigned_to is a random active support agent, and an unassigned ticket is
        always left OPEN, since nothing is actually working it yet.
        """
        support_agents = [u for u in users if u.is_support and u.is_active]
        openers = [u for u in users if not u.is_support]
        if not openers:
            return

        for _ in range(TICKET_COUNT):
            opener = random.choice(openers)
            agent = random.choice(support_agents) if support_agents and random.random() < 0.8 else None
            status = (
                Ticket.StatusChoices.OPEN
                if agent is None
                else random.choices(
                    [Ticket.StatusChoices.OPEN, Ticket.StatusChoices.IN_PROGRESS, Ticket.StatusChoices.CLOSED],
                    weights=[2, 3, 5],
                )[0]
            )

            try:
                with transaction.atomic():
                    ticket = Ticket.objects.create(
                        user=opener,
                        assigned_to=agent,
                        subject=random.choice(TICKET_SUBJECTS),
                        status=status,
                    )
                    Message.objects.create(
                        ticket=ticket, sender=opener, body=random.choice(TICKET_OPENING_MESSAGES)
                    )
                    if agent is not None and status != Ticket.StatusChoices.OPEN:
                        for _ in range(random.randint(1, 3)):
                            sender = agent if random.random() < 0.5 else opener
                            Message.objects.create(
                                ticket=ticket, sender=sender, body=random.choice(TICKET_REPLY_MESSAGES)
                            )
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f"Skipping a support ticket: {exc}"))

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
