from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import generics
from .serializers import UserRegisterSerializer

import logging
logger = logging.getLogger(__name__)


class LoggingTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        logger.info("JWT login attempt from %s", request.META.get("REMOTE_ADDR"))
        logger.debug("payload=%s", {k: v for k, v in request.data.items() if k != "password"})
        response = super().post(request, *args, **kwargs)
        logger.info("JWT login result status=%s", response.status_code)
        return response


class LoggingTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        logger.info("JWT refresh attempt from %s", request.META.get("REMOTE_ADDR"))
        response = super().post(request, *args, **kwargs)
        logger.info("JWT refresh result status=%s", response.status_code)
        return response

class RegisterUserView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer

    def perform_create(self, serializer):
        logger.info("users.RegisterUserView: registration requested from %s",
                    self.request.META.get("REMOTE_ADDR"))
        safe_data = {k: v for k, v in self.request.data.items() if k not in ["password"]}
        logger.debug("users.RegisterUserView: payload=%s", safe_data)
        user = serializer.save()
        logger.info("users.RegisterUserView: registration completed for user=%s", user.id)
        return user

