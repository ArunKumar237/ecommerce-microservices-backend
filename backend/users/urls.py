from django.urls import path
from .views import token_obtain_pair, token_refresh, RegisterUserView, ping

urlpatterns = [
    path("register/", RegisterUserView.as_view()),
    path("login/", token_obtain_pair),
    path("refresh/", token_refresh),
    path("ping/", ping),
]
