from django.urls import path
from . import views
from .views import ListingListView, ListingDetailView, catalog

urlpatterns = [
    path('function', views.catalog),
    path('listings/', ListingListView.as_view(), name="listing-list"),
    path('listings/<int:pk>/', ListingDetailView.as_view(), name='listing-detail'),
]