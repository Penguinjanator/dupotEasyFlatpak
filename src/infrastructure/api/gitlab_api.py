import re
import urllib.parse

from infrastructure.api.forge_api import ForgeApi


class GitlabApi(ForgeApi):

    NAME = "GitLab"
    DEFAULT_HOST = "gitlab.com"
    ALLOW_NESTED_OWNER = True

    # Files uploaded in the release notes: [name.flatpak](/uploads/…/name.flatpak)
    _UPLOAD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+\.flatpak)\)")

    def _list_releases(self, owner: str, repo: str, limit: int, page: int) -> list | None:
        project = urllib.parse.quote(f"{owner}/{repo}", safe="")
        return self._get_json(
            f"https://{self.host}/api/v4/projects/{project}/releases"
            f"?per_page={limit}&page={page}"
        )

    @staticmethod
    def _is_prerelease(release_obj: dict) -> bool:
        return bool(release_obj.get("upcoming_release"))

    def _extract_flatpak_asset(self, release_obj: dict, owner: str, repo: str) -> dict | None:
        tag_name = release_obj.get("tag_name", "")
        body = release_obj.get("description") or ""

        candidates = []
        for link in (release_obj.get("assets") or {}).get("links", []):
            name = link.get("name", "")
            url = link.get("direct_asset_url") or link.get("url", "")
            if name.endswith(".flatpak") or url.endswith(".flatpak"):
                asset_name = name if name.endswith(".flatpak") else url.rsplit("/", 1)[-1]
                candidates.append((asset_name, url))

        if not candidates:
            for url in self._UPLOAD_LINK_RE.findall(body):
                if url.startswith("/uploads/"):
                    url = self.project_url(owner, repo) + url
                elif url.startswith("/"):
                    url = f"https://{self.host}{url}"
                candidates.append((urllib.parse.unquote(url.rsplit("/", 1)[-1]), url))

        picked = self._pick_flatpak_asset(candidates)
        if not picked:
            return None
        return self._build_release_info(tag_name, picked[0], picked[1], body)
