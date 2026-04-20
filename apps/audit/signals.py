"""
Auto-audit signals.

Hooks into post_save / post_delete for every model in the audited apps
(surveys, responses, users) and writes AuditLog rows.

Strategy for UPDATE diffs:
  pre_save  → fetch current DB row, stash serialised state on instance._audit_pre
  post_save → compare stashed state against new state, write changes dict
"""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.audit.middleware import get_current_ip, get_current_user, get_current_user_agent

# App labels whose models are audited. Exclude 'audit' to prevent recursion.
_AUDITED_APP_LABELS = {"surveys", "responses", "users"}

# Fields whose values are never included in the diff (security / noise).
_SKIP_FIELDS = {"password", "value_encrypted", "_state"}


def _should_audit(sender):
    return sender._meta.app_label in _AUDITED_APP_LABELS


def _serialize_instance(instance):
    """Return a plain dict of field_name -> str(value) for diffing."""
    data = {}
    for field in instance._meta.fields:
        if field.name in _SKIP_FIELDS:
            continue
        try:
            value = field.value_from_object(instance)
            data[field.name] = str(value) if value is not None else None
        except Exception:
            pass
    return data


def _compute_diff(old, new):
    """Return {field: [old_val, new_val]} for fields that changed."""
    if old is None:
        # CREATE — record all non-null new values
        return {k: [None, v] for k, v in new.items() if v is not None}
    changes = {}
    all_keys = set(old) | set(new)
    for key in all_keys:
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = [old_val, new_val]
    return changes


def _write_log(action, sender, instance, changes):
    from apps.audit.models import AuditLog  # local import to avoid circular at load time

    AuditLog.objects.create(
        user=get_current_user(),
        action=action,
        model_name=sender.__name__,
        object_id=str(instance.pk),
        changes=changes,
        ip_address=get_current_ip(),
        user_agent=get_current_user_agent(),
    )


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

@receiver(pre_save)
def _capture_pre_save_state(sender, instance, **kwargs):
    if not _should_audit(sender):
        return
    if instance.pk:
        try:
            db_instance = sender.objects.get(pk=instance.pk)
            instance._audit_pre = _serialize_instance(db_instance)
        except sender.DoesNotExist:
            instance._audit_pre = None
    else:
        instance._audit_pre = None


@receiver(post_save)
def _log_save(sender, instance, created, **kwargs):
    if not _should_audit(sender):
        return
    action = "create" if created else "update"
    old = None if created else getattr(instance, "_audit_pre", None)
    new = _serialize_instance(instance)
    changes = _compute_diff(old, new)
    _write_log(action, sender, instance, changes)


@receiver(post_delete)
def _log_delete(sender, instance, **kwargs):
    if not _should_audit(sender):
        return
    snapshot = _serialize_instance(instance)
    changes = {k: [v, None] for k, v in snapshot.items() if v is not None}
    _write_log("delete", sender, instance, changes)
