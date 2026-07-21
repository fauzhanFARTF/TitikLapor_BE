"""Serializer pengguna & instansi."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from users.models import Instansi, User


class InstansiSerializer(serializers.ModelSerializer):
    jumlah_petugas = serializers.IntegerField(read_only=True)

    class Meta:
        model = Instansi
        fields = (
            "id",
            "nama",
            "kode",
            "deskripsi",
            "email_kontak",
            "telepon",
            "is_active",
            "jumlah_petugas",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "jumlah_petugas")


class UserSerializer(serializers.ModelSerializer):
    """Representasi baca — tidak pernah memuat password."""

    instansi_nama = serializers.CharField(source="instansi.nama", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "nama_lengkap",
            "nomor_telepon",
            "role",
            "role_label",
            "instansi",
            "instansi_nama",
            "foto",
            "is_active",
            "created_at",
        )
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class RegisterWargaSerializer(serializers.Serializer):
    email = serializers.EmailField()
    nama_lengkap = serializers.CharField(max_length=150)
    nomor_telepon = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_konfirmasi = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_konfirmasi"]:
            raise serializers.ValidationError(
                {"password_konfirmasi": "Konfirmasi kata sandi tidak cocok."}
            )
        return attrs


class CreateInternalUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    nama_lengkap = serializers.CharField(max_length=150)
    nomor_telepon = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
    role = serializers.ChoiceField(choices=[User.Role.PETUGAS, User.Role.ADMIN])
    instansi_id = serializers.UUIDField(required=False, allow_null=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("nama_lengkap", "nomor_telepon", "foto")


class ChangePasswordSerializer(serializers.Serializer):
    password_lama = serializers.CharField(write_only=True)
    password_baru = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
