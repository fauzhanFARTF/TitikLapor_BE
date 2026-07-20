"""Base model yang diwarisi seluruh app internal."""

import uuid

from django.db import models
from django.utils import timezone

from core.managers import SoftDeleteManager


class TimeStampedModel(models.Model):
    """Menyimpan jejak waktu pembuatan & pembaruan baris."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Primary key UUID — ID laporan tidak boleh mudah ditebak (enumerasi)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Penghapusan logis agar riwayat laporan tetap dapat diaudit."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager(include_deleted=True)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):  # type: ignore[override]
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """Kombinasi standar: UUID + timestamp + soft delete."""

    class Meta:
        abstract = True
