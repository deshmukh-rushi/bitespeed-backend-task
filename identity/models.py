from django.db import models


class Contact(models.Model):
    class ContactType(models.TextChoices):
        PRIMARY = "primary", "Primary"
        SECONDARY = "secondary", "Secondary"

    id = models.AutoField(primary_key=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    # This links a 'secondary' record back to its 'primary' record
    linked_id = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_contacts",
    )

    link_precedence = models.CharField(max_length=10, choices=ContactType.choices)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"ID: {self.id} - {self.email or self.phone_number}"
