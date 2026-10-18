from infrastructure.api.forge_api import ForgeApi


class GithubApi(ForgeApi):

    NAME = "GitHub"
    DEFAULT_HOST = "github.com"

    def _get_json(self, url: str, accept: str = "application/vnd.github+json") -> object | None:
        return super()._get_json(url, accept)

    def _list_releases(self, owner: str, repo: str, limit: int, page: int) -> list | None:
        return self._get_json(
            f"https://api.github.com/repos/{owner}/{repo}/releases"
            f"?per_page={limit}&page={page}"
        )
