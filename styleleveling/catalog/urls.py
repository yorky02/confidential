from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views
from .views import (
    ListingListView,
    ListingDetailView,
    MemberSignupView,
    SavedDealListCreateView,
    SavedDealDestroyView,
    ListingReviewListCreateView,
    StoreRequestCreateView,
    catalog,
)

urlpatterns = [
    path('function', views.catalog),
    path('listings/', ListingListView.as_view(), name="listing-list"),
    path('listings/<int:pk>/', ListingDetailView.as_view(), name='listing-detail'),
    path('members/signup/', MemberSignupView.as_view(), name='member-signup'),
    path('members/login/', obtain_auth_token, name='member-login'),
    path('saved-deals/', SavedDealListCreateView.as_view(), name='saved-deal-list'),
    path('saved-deals/<int:pk>/', SavedDealDestroyView.as_view(), name='saved-deal-detail'),
    path('listings/<int:listing_pk>/reviews/', ListingReviewListCreateView.as_view(), name='listing-review-list'),
    path('store-requests/', StoreRequestCreateView.as_view(), name='store-request-create'),
]
