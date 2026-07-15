from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SearchHistory(models.Model):
    """A logged search query, tied to a user or left anonymous for guests."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_history",
    )
    search_query = models.CharField(_("search query"), max_length=255)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("search history entry")
        verbose_name_plural = _("search history")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """
        :return: the logged search query.
        """
        return self.search_query
