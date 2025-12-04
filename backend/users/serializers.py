from rest_framework import serializers
from .models import User

class UserRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "password", "email", "role")
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User(
            username=validated_data["username"],
            email=validated_data["email"],
        )
        user.set_password(validated_data["password"])

        # Superuser case: fix admin role
        if validated_data.get("is_superuser") or validated_data.get("is_staff"):
            user.role = "admin"
        else:
            user.role = validated_data.get("role", "customer")

        user.save()
        return user
