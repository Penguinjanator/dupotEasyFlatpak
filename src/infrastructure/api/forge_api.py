import http.client
import json
import os
import platform
import re
import shutil
import urllib.request

_USER_AGENT = "dupotEasyFlatpak"

# Architecture aliases found in release asset filenames.
_ARCH_ALIASES = {
    "x86_64": ("x86_64", "amd64", "x64"),
    "aarch64": ("aarch64", "arm64"),
    "armv7l": ("armhf", "armv7"),
    "i686": ("i386", "i686", "x86_32"),
}

# Forge sub-pages that may follow owner/repo in a pasted URL. Needed for
# GitLab, where nested groups make the repo depth unknown.
_SUBPAGES = {
    "tree", "blob", "raw", "releases", "tags", "commits", "commit",
    "issues", "merge_requests", "pulls", "wiki", "pipelines", "activity",
}

_NETWORK_ERRORS = (OSError, http.client.HTTPException, ValueError)


class ForgeApi:
    """Common base for git forges publishing .flatpak release assets
    (GitHub, GitLab, Codeberg/Forgejo/Gitea)."""

    NAME = ""
    DEFAULT_HOST = ""
    # GitLab allows nested groups (group/subgroup/repo); others are owner/repo.
    ALLOW_NESTED_OWNER = False

    _URL_RE = re.compile(
        r"^(?:[a-z+]+://)?(?:[^@/\s]+@)?(?:www\.)?([^/:\s]+)(?::\d+)?[:/]+(.+?)/?$",
        re.IGNORECASE,
    )

    def __init__(self, host: str | None = None):
        self.host = (host or self.DEFAULT_HOST).lower()

    @classmethod
    def split_url(cls, url: str) -> tuple | None:
        match = cls._URL_RE.match((url or "").strip())
        if not match:
            return None
        return match.group(1).lower(), match.group(2)

    def parse_owner_repo(self, url: str) -> tuple | None:
        split = self.split_url(url)
        if not split:
            return None
        host, path = split
        if host != self.host:
            return None

        # Drop forge sub-pages (".../-/releases", ".../releases/tag/v1", ...).
        path = path.split("/-/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            return None
        if self.ALLOW_NESTED_OWNER:
            for i, part in enumerate(parts[2:], start=2):
                if part.lower() in _SUBPAGES:
                    parts = parts[:i]
                    break
            owner, repo = "/".join(parts[:-1]), parts[-1]
        else:
            owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        if not repo:
            return None
        return owner, repo

    def project_url(self, owner: str, repo: str) -> str:
        return f"https://{self.host}/{owner}/{repo}"

    def _get_json(self, url: str, accept: str = "application/json") -> object | None:
        req = urllib.request.Request(
            url, headers={"Accept": accept, "User-Agent": _USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode())
        except _NETWORK_ERRORS:
            return None

    @staticmethod
    def _build_release_info(tag_name: str, asset_name: str, download_url: str, body: str) -> dict:
        body = (body or "").strip()
        # A short, useful subtitle — repeating the asset filename on every
        # row is pointless. Use the first non-empty line of the release
        # notes; the expander reveals the rest.
        summary = ""
        for line in body.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                summary = line
                break
        if len(summary) > 100:
            summary = summary[:99].rstrip() + "…"

        return {
            "tag_name": tag_name or "",
            "asset_name": asset_name,
            "download_url": download_url,
            "body": body,
            "summary": summary,
        }

    def _list_releases(self, owner: str, repo: str, limit: int, page: int) -> list | None:
        """Raw release objects (newest first) for one page."""
        raise NotImplementedError

    @staticmethod
    def _pick_flatpak_asset(candidates: list[tuple]) -> tuple | None:
        """Among (name, url) .flatpak candidates, prefer the one built for
        this machine's arch; skip ones explicitly built for another arch."""
        if not candidates:
            return None
        machine = platform.machine().lower()
        own_aliases = _ARCH_ALIASES.get(machine, (machine,))
        other_aliases = [
            alias
            for arch, aliases in _ARCH_ALIASES.items()
            if arch != machine
            for alias in aliases
        ]

        def mentions(name, aliases):
            lowered = name.lower()
            return any(
                re.search(rf"(?:^|[^a-z0-9]){re.escape(alias)}(?:$|[^a-z0-9])", lowered)
                for alias in aliases
            )

        for candidate in candidates:
            if mentions(candidate[0], own_aliases):
                return candidate
        for candidate in candidates:
            if not mentions(candidate[0], other_aliases):
                return candidate
        return None

    def _extract_flatpak_asset(self, release_obj: dict, owner: str, repo: str) -> dict | None:
        # GitHub-shaped release (also Gitea/Forgejo): assets[].browser_download_url
        candidates = [
            (asset.get("name", ""), asset.get("browser_download_url", ""))
            for asset in release_obj.get("assets") or []
            if asset.get("name", "").endswith(".flatpak")
        ]
        picked = self._pick_flatpak_asset(candidates)
        if not picked:
            return None
        return self._build_release_info(
            release_obj.get("tag_name", ""), picked[0], picked[1], release_obj.get("body")
        )

    @staticmethod
    def _is_prerelease(release_obj: dict) -> bool:
        return bool(release_obj.get("prerelease") or release_obj.get("draft"))

    def get_latest_release_flatpak_asset(self, owner: str, repo: str) -> dict | None:
        data = self._list_releases(owner, repo, 20, 1)
        if not isinstance(data, list):
            return None
        for release_obj in data:
            if self._is_prerelease(release_obj):
                continue
            asset = self._extract_flatpak_asset(release_obj, owner, repo)
            if asset:
                return asset
        return None

    def get_releases_with_flatpak_asset(
        self, owner: str, repo: str, limit: int = 10, page: int = 1
    ) -> list[dict]:
        """One page of releases (newest first) that publish a .flatpak
        asset — `limit` per page, `page` starting at 1."""
        data = self._list_releases(owner, repo, limit, page)
        if not isinstance(data, list):
            return []

        releases = []
        for release_obj in data:
            asset = self._extract_flatpak_asset(release_obj, owner, repo)
            if asset:
                releases.append(asset)
        return releases

    def download_asset(self, download_url: str, dest_path: str) -> bool:
        if not download_url:
            return False

        req = urllib.request.Request(
            download_url,
            headers={
                "Accept": "application/octet-stream",
                "User-Agent": _USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                with open(dest_path, "wb") as f:
                    shutil.copyfileobj(response, f)
        except _NETWORK_ERRORS:
            return False

        # A "successful" request that came back empty (redirect not followed
        # correctly, rate-limited HTML error page, ...) is still a failure —
        # don't let an empty/corrupt bundle reach the install step.
        return os.path.getsize(dest_path) > 0


def get_forge_api(url: str) -> ForgeApi | None:
    """Pick the forge API matching a project URL's host, or None."""
    from infrastructure.api.gitea_api import GiteaApi
    from infrastructure.api.github_api import GithubApi
    from infrastructure.api.gitlab_api import GitlabApi

    split = ForgeApi.split_url(url)
    if not split:
        return None
    host = split[0]

    if host == "github.com":
        api = GithubApi(host)
    elif host == "codeberg.org" or "gitea" in host or "forgejo" in host:
        api = GiteaApi(host)
    elif "gitlab" in host:
        api = GitlabApi(host)
    else:
        return None

    return api if api.parse_owner_repo(url) else None


def parse_forge_url(url: str) -> tuple | None:
    """(api, owner, repo) for a supported forge project URL, or None."""
    api = get_forge_api(url)
    if not api:
        return None
    owner, repo = api.parse_owner_repo(url)
    return api, owner, repo
