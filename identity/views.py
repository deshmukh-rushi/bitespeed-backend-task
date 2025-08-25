from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contact


class IdentifyAPIView(APIView):

    @transaction.atomic
    def post(self, request):
        email = request.data.get("email")
        phone_number = (
            str(request.data.get("phoneNumber"))
            if request.data.get("phoneNumber")
            else None
        )

        matching_contacts = Contact.objects.filter(
            Q(email=email) | Q(phone_number=phone_number)
        ).order_by("created_at")

        if not matching_contacts.exists():
            contact = Contact.objects.create(
                email=email,
                phone_number=phone_number,
                link_precedence=Contact.ContactType.PRIMARY,
            )
            return Response(self.format_response([contact]), status=status.HTTP_200_OK)

        primary_contact_ids = set()
        for c in matching_contacts:
            if c.link_precedence == Contact.ContactType.PRIMARY:
                primary_contact_ids.add(c.id)
            elif c.linked_id_id:
                primary_contact_ids.add(c.linked_id_id)

        all_related_contacts = (
            Contact.objects.filter(
                Q(id__in=primary_contact_ids) | Q(linked_id__in=primary_contact_ids)
            )
            .distinct()
            .order_by("created_at")
        )

        primary_contact = all_related_contacts.first()

        secondary_to_update = all_related_contacts.filter(
            link_precedence=Contact.ContactType.PRIMARY
        ).exclude(id=primary_contact.id)

        if secondary_to_update.exists():
            secondary_to_update.update(
                linked_id=primary_contact, link_precedence=Contact.ContactType.SECONDARY
            )

        has_new_email = email and not all_related_contacts.filter(email=email).exists()
        has_new_phone = (
            phone_number
            and not all_related_contacts.filter(phone_number=phone_number).exists()
        )

        if has_new_email or has_new_phone:
            Contact.objects.create(
                email=email,
                phone_number=phone_number,
                linked_id=primary_contact,
                link_precedence=Contact.ContactType.SECONDARY,
            )

        final_contacts = Contact.objects.filter(
            Q(id=primary_contact.id) | Q(linked_id=primary_contact.id)
        ).order_by("created_at")

        return Response(self.format_response(final_contacts), status=status.HTTP_200_OK)

    def format_response(self, contacts):
        if not contacts:
            return {}

        primary_contact = contacts[0]

        if primary_contact.link_precedence == Contact.ContactType.SECONDARY:
            primary_contact = primary_contact.linked_id

        final_contacts = Contact.objects.filter(
            Q(id=primary_contact.id) | Q(linked_id=primary_contact.id)
        ).order_by("created_at")

        emails = list(dict.fromkeys(c.email for c in final_contacts if c.email))
        phone_numbers = list(
            dict.fromkeys(c.phone_number for c in final_contacts if c.phone_number)
        )

        secondary_contact_ids = [
            c.id
            for c in final_contacts
            if c.link_precedence == Contact.ContactType.SECONDARY
        ]

        return {
            "contact": {
                "primaryContatctId": primary_contact.id,
                "emails": emails,
                "phoneNumbers": phone_numbers,
                "secondaryContactIds": secondary_contact_ids,
            }
        }
