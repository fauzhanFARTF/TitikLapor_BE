"""Manager & queryset bersama untuk pola soft-delete."""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet yang menandai baris terhapus alih-alih menghapus fisik."""

    def delete(self):  # type: ignore[override]
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Manager default: hanya mengembalikan baris yang belum dihapus."""

    def __init__(self, *args, include_deleted: bool = False, **kwargs):
        self._include_deleted = include_deleted
        super().__init__(*args, **kwargs)

    def get_queryset(self) -> SoftDeleteQuerySet:
        qs = SoftDeleteQuerySet(self.model, using=self._db)
        return qs if self._include_deleted else qs.alive()
