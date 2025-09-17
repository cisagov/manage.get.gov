# registrar/management/commands/restore_approved_requests.py
from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.db import transaction
from django.apps import apps
from auditlog.models import LogEntry
from registrar.models import DomainRequest, Domain, DomainInformation

S = DomainRequest.DomainRequestStatus


def last_soft_delete_event_for_domain(name: str):
    """
    Returns (timestamp, actor_repr, details) for the most recent audit log
    that suggests this domain was deleted/soft-deleted, else None.
    """
    ct = ContentType.objects.get_for_model(Domain)
    # find Domain by name (any state)
    dom = Domain.objects.filter(name=name).first()
    if not dom:
        return None

    # Look for a state->DELETED change or a new 'deleted' timestamp
    qs = LogEntry.objects.filter(content_type=ct, object_id=dom.pk).order_by("-timestamp")
    for le in qs:
        ch = le.changes_dict or {}
        state_change = ch.get("state")
        deleted_change = ch.get("deleted")
        if (state_change and state_change[-1] == Domain.State.DELETED) or deleted_change:
            actor = getattr(le.actor, "email", None) or getattr(le.actor, "username", None) or str(le.actor_id)
            details = []
            if state_change:
                details.append(f"state: {state_change[0]} → {state_change[1]}")
            if deleted_change:
                details.append(f"deleted ts: {deleted_change[0]} → {deleted_change[1]}")
            return (le.timestamp, actor, "; ".join(details))
    return None


class Command(BaseCommand):
    help = (
        "Restore DomainRequests that were approved and later demoted; "
        "recreate Domain/DomainInformation and ensure there is a MANAGER role. "
        "Use --domains to target specific domain names."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only; make no DB changes.")
        parser.add_argument(
            "--domains",
            nargs="+",
            help=(
                "Space-separated list of domain names to restore (e.g. lonewolfok.gov other.gov). "
                "If omitted, candidates are discovered from audit logs."
            ),
        )
        parser.add_argument(
            "--fallback-manager-email",
            help="Email of a user to assign MANAGER if the DomainRequest has no creator "
            "(e.g. cameron.dixon@cisa.dhs.gov).",
        )

    def last_soft_delete_event_for_domain(name: str):
        """
        Returns (timestamp, actor_repr, details) for the most recent audit log
        that suggests this domain was deleted/soft-deleted, else None.
        """
        ct = ContentType.objects.get_for_model(Domain)
        # find Domain by name (any state)
        dom = Domain.objects.filter(name=name).first()
        if not dom:
            return None

        # Look for a state->DELETED change or a new 'deleted' timestamp
        qs = LogEntry.objects.filter(content_type=ct, object_id=dom.pk).order_by("-timestamp")
        for le in qs:
            ch = le.changes_dict or {}
            state_change = ch.get("state")
            deleted_change = ch.get("deleted")
            if (state_change and state_change[-1] == Domain.State.DELETED) or deleted_change:
                actor = getattr(le.actor, "email", None) or getattr(le.actor, "username", None) or str(le.actor_id)
                details = []
                if state_change:
                    details.append(f"state: {state_change[0]} → {state_change[1]}")
                if deleted_change:
                    details.append(f"deleted ts: {deleted_change[0]} → {deleted_change[1]}")
                return (le.timestamp, actor, "; ".join(details))
        return None

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        tag = "[DRY]" if dry else ""
        domains = opts.get("domains") or []
        fallback_email = (opts.get("fallback_manager_email") or "").strip()

        User = get_user_model()
        fallback_user = None
        if fallback_email:
            fallback_user = User.objects.filter(email__iexact=fallback_email).first()
            if not fallback_user:
                self.stdout.write(
                    self.style.WARNING(f"[fallback] No user found for {fallback_email}; fallback will be skipped.")
                )

        UserDomainRole = apps.get_model("registrar", "UserDomainRole")
        ct_id = ContentType.objects.get(app_label="registrar", model="domainrequest").id

        if domains:
            qs = (
                DomainRequest.objects.select_related("requested_domain", "approved_domain", "creator")
                .filter(requested_domain__name__in=domains)
                .exclude(status=S.APPROVED)
                .order_by("-updated_at")
            )
        else:
            approved_once_ids = (
                LogEntry.objects.filter(content_type_id=ct_id, changes__status__1=S.APPROVED)
                .values_list("object_id", flat=True)
                .distinct()
            )
            qs = (
                DomainRequest.objects.select_related("requested_domain", "approved_domain", "creator")
                .filter(pk__in=approved_once_ids)
                .exclude(status=S.APPROVED)
                .order_by("-updated_at")
            )

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No stale demotions detected."))
            return

        self.stdout.write(f"Candidates: {qs.count()}")

        restored = 0

        for dr in qs:
            name = getattr(getattr(dr, "requested_domain", None), "name", None)
            if not name:
                self.stdout.write(self.style.WARNING(f"[{dr.pk}] No requested_domain.name; skipping."))
                continue

            approval_log = (
                LogEntry.objects.filter(content_type_id=ct_id, object_id=dr.pk, changes__status__1=S.APPROVED)
                .order_by("-timestamp")
                .first()
            )

            existing_dom = Domain.objects.filter(name=name).exclude(state=Domain.State.DELETED).first()
            dom_will_be_created = existing_dom is None

            if existing_dom is None:
                self.stdout.write(
                    self.style.WARNING(f"[{name}] MISSING Domain (non-DELETED). Will CREATE a new Domain row.")
                )
                hint = last_soft_delete_event_for_domain(name)
                if hint:
                    ts, who, details = hint
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{name}] Audit hint: previously deleted/soft-deleted at {ts} by {who} ({details})."
                        )
                    )
                else:
                    self.stdout.write(self.style.WARNING(f"[{name}] No audit hint found for prior deletion."))
            else:
                self.stdout.write(f"[{name}] Found existing Domain id={existing_dom.id} (state={existing_dom.state}).")

            # check DomainInformation exist
            info_exists = False
            if existing_dom:
                info_exists = DomainInformation.objects.filter(domain=existing_dom).exists()
                if not info_exists:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{name}] MISSING DomainInformation. Will CREATE a new DomainInformation row."
                        )
                    )
                else:
                    self.stdout.write(f"[{name}] Found DomainInformation for Domain id={existing_dom.id}.")

            # Pick manager user: creator > fallback = cameron
            manager_user = dr.creator if dr.creator_id else fallback_user
            manager_desc = f"user_id={manager_user.id} ({manager_user.email})" if manager_user else "none (skip)"

            # Role only if we can evaluate against an existing domain
            role_exists = False
            if manager_user and existing_dom:
                role_exists = UserDomainRole.objects.filter(
                    user=manager_user, domain=existing_dom, role=UserDomainRole.Roles.MANAGER
                ).exists()

            self.stdout.write(f"{tag} Edits for {name}:")
            self.stdout.write(f"{tag}  - Domain: {'create' if dom_will_be_created else 'reuse'}")
            self.stdout.write(
                f"{tag}  - DomainInformation: {'create' if (dom_will_be_created or not info_exists) else 'reuse'}"
            )
            self.stdout.write(
                f"{tag}  - Manager role: "
                f"{('create' if (dom_will_be_created or not role_exists) else 'reuse') if manager_user else 'skip'} "
                f"({manager_desc})"
            )
            self.stdout.write(f"{tag}  - Status: {dr.status} → {S.APPROVED}")

            if not dry:
                confirm = input(f"Restore {name} now? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes"):
                    self.stdout.write(self.style.WARNING(f"[skip] Skipped restoring {name}"))
                    continue
            if dry:
                self.stdout.write(
                    self.style.SUCCESS(f"[DRY] Would restore {name} → APPROVED and ensure Domain/Info/Role")
                )
                restored += 1
                continue

            try:
                with transaction.atomic():
                    # Domain
                    if existing_dom:
                        dom = existing_dom
                        self.stdout.write(f"[use] Domain {name} (id={dom.id})")
                    else:
                        dom = Domain.objects.create(name=name)
                        self.stdout.write(f"[create] Domain {name} (id={dom.id})")

                    # DomainInformation
                    if not DomainInformation.objects.filter(domain=dom).exists():
                        DomainInformation.create_from_dr(domain_request=dr, domain=dom)
                        self.stdout.write(f"[create] DomainInformation for {name}")
                    else:
                        self.stdout.write(f"[use] DomainInformation for {name}")

                    # Manager role (creator or fallback)
                    if manager_user:
                        created_role = UserDomainRole.objects.get_or_create(
                            user=manager_user, domain=dom, role=UserDomainRole.Roles.MANAGER
                        )[1]
                        self.stdout.write(
                            ("[create] " if created_role else "[use] ") + f"MANAGER role for {manager_desc} on {name}"
                        )
                    else:
                        self.stdout.write("[skip] MANAGER role (no creator and no fallback user)")

                    # Flip status + link domain + backfill last_status_update when possible
                    old_status = dr.status
                    existing_for_domain = DomainRequest.objects.filter(approved_domain=dom).exclude(pk=dr.pk).first()

                    if existing_for_domain:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[{name}] Another request {existing_for_domain.pk} already owns approved_domain={dom.id}; skipping re-link."
                            )
                        )
                        continue

                    dr.approved_domain = dom
                    dr.status = S.APPROVED
                    if approval_log:
                        try:
                            dr.last_status_update = approval_log.timestamp.date()
                        except Exception:
                            pass
                    dr.save(update_fields=["approved_domain", "status", "last_status_update", "updated_at"])
                    self.stdout.write(f"[status] {old_status} → {dr.status}")

                self.stdout.write(self.style.SUCCESS(f"[OK] Restored {name}"))
                restored += 1
            except Exception as e:
                raise CommandError(f"[{name or dr.pk}] restore failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"Done. Restored {restored} request(s)."))
