from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import generics
from .serializers import UserRegisterSerializer

token_obtain_pair = TokenObtainPairView.as_view()
token_refresh = TokenRefreshView.as_view()

class RegisterUserView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer

def ping(request):
    return JsonResponse({"ok": True, "app": "users"})
