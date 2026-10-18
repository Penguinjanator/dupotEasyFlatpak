from infrastructure.api.forge_api import ForgeApi


class GiteaApi(ForgeApi):
    """Codeberg / Forgejo / Gitea — release objects share GitHub's shape."""

    NAME = "Codeberg"
    DEFAULT_HOST = "codeberg.org"

    def __init__(self, host: str | None = None):
        super().__init__(host)
        if self.host != self.DEFAULT_HOST:
            self.NAME = "Forgejo/Gitea"

    def _list_releases(self, owner: str, repo: str, limit: int, page: int) -> list | None:
        return self._get_json(
            f"https://{self.host}/api/v1/repos/{owner}/{repo}/releases"
            f"?limit={limit}&page={page}"
        )
