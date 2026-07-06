from django.core.management.base import BaseCommand
from faker import Faker
# from users.models import User
# from listings.models import Listing
# from bookings.models import Booking
# from reviews.models import Review

class Command(BaseCommand):
    """
    A Django management command to fill the database with tests data.
    """
    help = 'Fill the database with test data'

    def handle(self, *args, **kwargs):
        fake = Faker()

        self.stdout.write(self.style.SUCCESS('Start filling database...'))

        # for _ in range(10):
        #     User.objects.create(username=fake.user_name(), email=fake.email())

        self.stdout.write(self.style.SUCCESS('Database filled successfully'))
