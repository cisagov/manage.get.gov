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
            help="Email of a user to assign MANAGER if the DomainRequest has no requester "
            "(e.g. cameron.dixon@cisa.dhs.gov).",
        )

    # -------- handle orchestration --------
    def handle(self, *args, **opts):
        dry = bool(opts["dry_run"])
        fallback_user = self._resolve_fallback_user(opts.get("fallback_manager_email"))
        user_domain_role_model = apps.get_model("registrar", "UserDomainRole")
        ct_id = ContentType.objects.get(app_label="registrar", model="domainrequest").id

        qs = self._build_queryset(opts.get("domains"), ct_id)
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

            plan = self._plan_restoration(dr, name, ct_id, user_domain_role_model, fallback_user)
            self._print_plan(plan, dry)

            if dry:
                self.stdout.write(
                    self.style.SUCCESS(f"[DRY] Would restore {name} → APPROVED and ensure Domain/Info/Role")
                )
                restored += 1
                continue

            if not self._confirm_restore(name):
                self.stdout.write(self.style.WARNING(f"[skip] Skipped restoring {name}"))
                continue

            try:
                self._perform_restore(plan, user_domain_role_model)
                self.stdout.write(self.style.SUCCESS(f"[OK] Restored {name}"))
                restored += 1
            except Exception as e:
                raise CommandError(f"[{name or dr.pk}] restore failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"Done. Restored {restored} request(s)."))

    # -------- helpers --------
    def _resolve_fallback_user(self, fallback_email: str | None):
        email = (fallback_email or "").strip()
        if not email:
            return None
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            self.stdout.write(self.style.WARNING(f"[fallback] No user found for {email}; fallback will be skipped."))
        return user

    def _build_queryset(self, domains: list[str] | None, ct_id: int):
        base = DomainRequest.objects.select_related("requested_domain", "approved_domain", "requester")
        if domains:
            return base.filter(requested_domain__name__in=domains).exclude(status=S.APPROVED).order_by("-updated_at")
        approved_once_ids = (
            LogEntry.objects.filter(content_type_id=ct_id, changes__status__1=S.APPROVED)
            .values_list("object_id", flat=True)
            .distinct()
        )
        return base.filter(pk__in=approved_once_ids).exclude(status=S.APPROVED).order_by("-updated_at")

    def _plan_restoration(self, dr, name: str, ct_id: int, UserDomainRole, fallback_user):
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

        info_exists = bool(existing_dom and DomainInformation.objects.filter(domain=existing_dom).exists())
        if existing_dom and not info_exists:
            self.stdout.write(
                self.style.WARNING(f"[{name}] MISSING DomainInformation. Will CREATE a new DomainInformation row.")
            )
        elif existing_dom and info_exists:
            self.stdout.write(f"[{name}] Found DomainInformation for Domain id={existing_dom.id}.")

        manager_user = dr.requester if dr.requester_id else fallback_user
        manager_desc = f"user_id={manager_user.id} ({manager_user.email})" if manager_user else "none (skip)"
        role_exists = bool(
            manager_user
            and existing_dom
            and UserDomainRole.objects.filter(
                user=manager_user, domain=existing_dom, role=UserDomainRole.Roles.MANAGER
            ).exists()
        )

        return {
            "dr": dr,
            "name": name,
            "approval_log": approval_log,
            "existing_dom": existing_dom,
            "dom_will_be_created": dom_will_be_created,
            "info_exists": info_exists,
            "manager_user": manager_user,
            "manager_desc": manager_desc,
            "role_exists": role_exists,
        }

    def _print_plan(self, plan: dict, dry: bool):
        tag = "[DRY]" if dry else ""
        self.stdout.write(f"{tag} Edits for {plan['name']}:")
        self.stdout.write(f"{tag}  - Domain: {'create' if plan['dom_will_be_created'] else 'reuse'}")
        self.stdout.write(
            f"{tag}  - DomainInformation: "
            f"{'create' if (plan['dom_will_be_created'] or not plan['info_exists']) else 'reuse'}"
        )
        mgr_action = (
            ("create" if (plan["dom_will_be_created"] or not plan["role_exists"]) else "reuse")
            if plan["manager_user"]
            else "skip"
        )
        self.stdout.write(f"{tag}  - Manager role: {mgr_action} ({plan['manager_desc']})")
        self.stdout.write(f"{tag}  - Status: {plan['dr'].status} → {S.APPROVED}")

    def _confirm_restore(self, name: str) -> bool:
        confirm = input(f"Restore {name} now? [y/N]: ").strip().lower()
        return confirm in ("y", "yes")

    def _perform_restore(self, plan: dict, UserDomainRole):
        dr = plan["dr"]
        name = plan["name"]
        approval_log = plan["approval_log"]
        manager_user = plan["manager_user"]

        with transaction.atomic():
            # Domain
            if plan["existing_dom"]:
                dom = plan["existing_dom"]
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

            # Manager role
            if manager_user:
                created_role = UserDomainRole.objects.get_or_create(
                    user=manager_user, domain=dom, role=UserDomainRole.Roles.MANAGER
                )[1]
                self.stdout.write(
                    ("[create] " if created_role else "[use] ")
                    + f"MANAGER role for user_id={manager_user.id} ({manager_user.email}) on {name}"
                )
            else:
                self.stdout.write("[skip] MANAGER role (no requester and no fallback user)")

            # Relink & status
            existing_for_domain = DomainRequest.objects.filter(approved_domain=dom).exclude(pk=dr.pk).first()
            if existing_for_domain:
                self.stdout.write(
                    self.style.WARNING(
                        f"Request {existing_for_domain.pk} already owns approved_domain={dom.id}; skipping re-link."
                    )
                )
                return

            old_status = dr.status
            dr.approved_domain = dom
            dr.status = S.APPROVED

            if approval_log:
                ts = getattr(approval_log, "timestamp", None)
                if ts is None:
                    self.stdout.write(
                        self.style.WARNING(f"[{name}] approval_log has no timestamp; last_status_update unchanged.")
                    )
                else:
                    try:
                        # ts is usually a datetime; accept date too.
                        dr.last_status_update = ts.date() if hasattr(ts, "date") else ts
                    except (AttributeError, TypeError, ValueError) as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[{name}] could not find last_status_update from approval_log timestamp ({ts!r}): {e}"
                            )
                        )

            dr.save(update_fields=["approved_domain", "status", "last_status_update", "updated_at"])
            self.stdout.write(f"[status] {old_status} → {dr.status}")
