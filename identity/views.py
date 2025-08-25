import logging

from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contact

logger = logging.getLogger(__name__)


class IdentifyAPIView(APIView):

    @transaction.atomic
    def post(self, request):
        """
        Handles the /identify endpoint.
        Consolidates contact information based on email or phone number.
        """
        logger.info(f"Identify request received with data: {request.data}")

        try:
            email = request.data.get("email")
            phone_number = (
                str(request.data.get("phoneNumber"))
                if request.data.get("phoneNumber")
                else None
            )

            # Basic input validation
            if not email and not phone_number:
                return Response(
                    {"error": "Either email or phoneNumber must be provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            matching_contacts = Contact.objects.filter(
                Q(email=email) | Q(phone_number=phone_number)
            ).order_by("created_at")

            if not matching_contacts.exists():
                # This is a new identity, create a primary contact.
                contact = Contact.objects.create(
                    email=email,
                    phone_number=phone_number,
                    link_precedence=Contact.ContactType.PRIMARY,
                )
                return Response(
                    self.format_response([contact]), status=status.HTTP_200_OK
                )

            # An identity already exists, consolidate all related contacts.
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

            # Merge if the request links two previously separate primary contacts.
            secondary_to_update = all_related_contacts.filter(
                link_precedence=Contact.ContactType.PRIMARY
            ).exclude(id=primary_contact.id)

            if secondary_to_update.exists():
                secondary_to_update.update(
                    linked_id=primary_contact,
                    link_precedence=Contact.ContactType.SECONDARY,
                )

            # Create a new secondary contact if the request introduces new information.
            has_new_email = (
                email and not all_related_contacts.filter(email=email).exists()
            )
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

            return Response(
                self.format_response(final_contacts), status=status.HTTP_200_OK
            )

        except Exception as e:
            # Log the full exception traceback for detailed debugging
            logger.error(
                f"An unexpected error occurred in /identify: {e}", exc_info=True
            )
            return Response(
                {"error": "An internal server error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def format_response(self, contacts):
        """
        Formats the consolidated contact information for the API response.
        """
        if not contacts:
            return {}

        primary_contact = contacts[0]

        # Ensure we are working with the true primary contact.
        if (
            primary_contact.link_precedence == Contact.ContactType.SECONDARY
            and primary_contact.linked_id
        ):
            primary_contact = primary_contact.linked_id

        # Re-fetch all contacts related to the true primary to build the final response.
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
