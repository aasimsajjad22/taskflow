from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.users.serializers import (
    PasswordChangeSerializer,
    UserProfileSerializer,
    UserRegisterSerializer,
)
from apps.users.services import user_change_password, user_create, user_update_profile


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    authentication_classes = []

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=UserRegisterSerializer, responses={200: UserProfileSerializer})
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        user = user_create(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
        )

        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserProfileSerializer)
    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

    @extend_schema(request=UserProfileSerializer, responses=UserProfileSerializer)
    def path(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)

        serializer.is_valid(raise_exception=True)

        user = user_update_profile(user=request.user, data=serializer.validated_data)

        return Response(UserProfileSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={204, None})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        user_change_password(
            user=request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )

        return Response(status=status.HTTP_204_NO_CONTENT)
