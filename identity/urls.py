from django.urls import path

from .views import IdentifyAPIView

urlpatterns = [
    path("identify", IdentifyAPIView.as_view(), name="identify"),
]
