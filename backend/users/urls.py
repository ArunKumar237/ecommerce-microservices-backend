from django.urls import path
from .views import RegisterUserView, LoggingTokenObtainPairView, LoggingTokenRefreshView

urlpatterns = [
    path("register/", RegisterUserView.as_view()),
    path('login/', LoggingTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', LoggingTokenRefreshView.as_view(), name='token_refresh'),
]
