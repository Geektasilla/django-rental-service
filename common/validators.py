from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

no_html_tags_validator = RegexValidator(
    regex=r"^[^<>]*$",
    message=_("This field may not contain the characters < or >."),
)
