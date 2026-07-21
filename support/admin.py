from django.contrib import admin

from .models import Message, Ticket


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "user", "assigned_to", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["subject", "user__email"]
    inlines = [MessageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "assigned_to")
