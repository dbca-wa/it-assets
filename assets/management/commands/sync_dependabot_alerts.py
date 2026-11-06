import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from github import Github
from github.Auth import Token

from assets.models import Repository


class Command(BaseCommand):
    help = "Synchronises GitHub Dependabot alerts for all repositories"

    logger = logging.getLogger("assets")

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            action="store",
            dest="url",
            default=None,
            help="Only sync the repository with this exact URL",
        )

    def handle(self, *args, **options):
        repositories = Repository.objects.all()
        url = options.get("url")
        if url:
            repositories = repositories.filter(url=url)
            if not repositories.exists():
                raise CommandError(f"No repository found with URL {url}")

        total = repositories.count()
        if total == 0:
            msg = "No repositories to sync"
            self.logger.info(msg)
            return

        github_client = self.get_github_client()
        synced = 0
        failed = 0
        advisories_total = 0

        for count, repository in enumerate(repositories, start=1):
            try:
                advisories = repository.sync_dependabot_alerts(github_client=github_client)
            except Exception as exc:
                # One broken repository (invalid URL, deleted repository, network error)
                # must not prevent the remaining repositories from syncing.
                failed += 1
                self.logger.warning(
                    f"[{count}/{total}] Failed to sync Dependabot alerts for {repository}: {exc}",
                    exc_info=exc,
                )
                continue

            synced += 1
            advisories_total += len(advisories)
            self.logger.info(f"[{count}/{total}] Synced {len(advisories)} advisories for {repository}")

        if synced == 0:
            raise CommandError(f"Failed to sync Dependabot alerts for all {total} repositories")

        summary = f"Dependabot sync complete: {synced}/{total} repositories synced, {failed} failed, {advisories_total} advisories"
        self.logger.info(summary)

    def get_github_client(self):
        """Build a single GitHub client shared across all repositories."""
        token = getattr(settings, "GITHUB_TOKEN", None)
        if token:
            return Github(auth=Token(token))

        self.logger.warning("GITHUB_TOKEN is not set; using an unauthenticated GitHub client")
        return Github()
