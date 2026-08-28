from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from rest_framework import generics, filters
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Listing, ListingReview, SavedDeal, Store, StoreRequest
from .serializers import (
    ListingSerializer,
    MemberSignupSerializer,
    SavedDealSerializer,
    ListingReviewSerializer,
    StoreRequestSerializer,
    StoreSerializer,
)
from django_filters.rest_framework import DjangoFilterBackend

# Create your views here.

def catalog(request):
    return HttpResponse("This page is getting updated...")

class ListingListView(generics.ListAPIView):
    serializer_class = ListingSerializer
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
        DjangoFilterBackend,
    ]
    filterset_fields = [
        'store',
        'product__category',
        'product__audience',
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

    def member_has_full_access(self):
        user = self.request.user
        return (
            user.is_authenticated
            and hasattr(user, "styleleveling_membership")
            and user.styleleveling_membership.has_full_access
        )

    def get_queryset(self):
        queryset = Listing.objects.select_related("store", "product").prefetch_related("images")
        if self.member_has_full_access():
            return queryset
        return queryset.filter(store__is_guest_visible=True)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if not self.member_has_full_access():
            if request.query_params.get("ordering") or request.query_params.get("store"):
                serializer = self.get_serializer(queryset[:100], many=True)
                return Response(serializer.data)
            store_ids = list(
                queryset.order_by().values_list("store_id", flat=True).distinct()
            )
            store_rows = {
                store_id: list(queryset.filter(store_id=store_id)[:100])
                for store_id in store_ids
            }
            queryset = []
            while len(queryset) < 100 and any(store_rows.values()):
                for store_id in store_ids:
                    if store_rows[store_id] and len(queryset) < 100:
                        queryset.append(store_rows[store_id].pop(0))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class StoreListView(generics.ListAPIView):
    serializer_class = StoreSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            Store.objects.filter(is_active=True, is_guest_visible=True)
            .annotate(
                listing_count=Count(
                    "listing",
                    filter=Q(listing__is_promo_active=True),
                    distinct=True,
                )
            )
            .filter(listing_count__gt=0)
            .order_by("store_name")
        )

class ListingDetailView(generics.RetrieveAPIView):
    serializer_class = ListingSerializer

    def get_queryset(self):
        queryset = Listing.objects.select_related("store", "product").prefetch_related("images")
        user = self.request.user
        has_full_access = (
            user.is_authenticated
            and hasattr(user, "styleleveling_membership")
            and user.styleleveling_membership.has_full_access
        )
        if has_full_access:
            return queryset
        return queryset.filter(store__is_guest_visible=True)


class MemberSignupView(generics.GenericAPIView):
    serializer_class = MemberSignupSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "email": user.email, "has_full_access": True},
            status=status.HTTP_201_CREATED,
        )


class SavedDealListCreateView(generics.ListCreateAPIView):
    serializer_class = SavedDealSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedDeal.objects.filter(user=self.request.user).select_related(
            "listing__store", "listing__product"
        ).prefetch_related("listing__images")


class SavedDealDestroyView(generics.DestroyAPIView):
    serializer_class = SavedDealSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedDeal.objects.filter(user=self.request.user)


class ListingReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ListingReviewSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get_queryset(self):
        return ListingReview.objects.filter(
            listing_id=self.kwargs["listing_pk"],
            is_approved=True,
        ).select_related("user")

    def perform_create(self, serializer):
        listing = get_object_or_404(Listing, pk=self.kwargs["listing_pk"])
        serializer.save(listing=listing)


class StoreRequestCreateView(generics.CreateAPIView):
    serializer_class = StoreRequestSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)

    
