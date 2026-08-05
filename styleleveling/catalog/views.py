from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import generics, filters
from .models import Listing
from .serializers import ListingSerializer
from django_filters.rest_framework import DjangoFilterBackend

# Create your views here.

def catalog(request):
    return HttpResponse("This page is getting updated...")

class ListingListView(generics.ListAPIView):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
        DjangoFilterBackend,
    ]
    filterset_fields = [
        'store',
        'product__category',
        'is_promo_active',
    ]
    search_fields = [
        'product__product_name',
        'product__brand_name',
        'store__store_name',
        'external_product_id',
    ]
    ordering_fields = [
        'current_price',
        'original_price',
        'last_checked_time',
        'last_seen',
    ]

    ordering = ['current_price']

class ListingDetailView(generics.RetrieveAPIView):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer

    