from rest_framework import serializers

from apps.users.models import User
from apps.users.serializers import UserSummarySerializer
from apps.workspaces.models import Membership, Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)

    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Workspace
        fields = ["id", "owner", "member_count", "name", "slug", "created_at", "updated_at"]

        read_only_fields = ["slug", "created_at", "updated_at"]


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    workspace = WorkspaceSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "workspace", "role", "created_at"]


class MembershipCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()

    role = serializers.ChoiceField(
        choices=[Membership.Role.ADMIN.value, Membership.Role.MEMBER.value],
        default=Membership.Role.MEMBER.value,
    )

    def validate(self, attrs):
        email = attrs.pop("email")
        user = User.objects.filter(email__iexact=email).first()

        if user is None:
            raise serializers.ValidationError("User does not exist")
        attrs["user"] = user

        return attrs
