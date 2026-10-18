import os
import shutil
import subprocess
import tempfile

from gi.repository import GLib

from infrastructure.api.flatpak_api import FlatpakApi
from infrastructure.api.forge_api import parse_forge_url
from infrastructure.repository.local_apps_repository import LocalAppsRepository


def _stream(cmd, output_fn) -> int:
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    for line in process.stdout:
        output_fn(line)
    return process.wait()


def install_bundle(file_path: str, scope_flag: str, output_fn, flatpak_api=None) -> bool:
    """Install a .flatpak bundle, first uninstalling the same ref when it
    comes from a signed remote (see FlatpakApi.get_bundle_conflict). If the
    bundle install then fails, the previous install is restored from its
    original remote. Blocking — call from a thread."""
    flatpak_api = flatpak_api or FlatpakApi()

    conflict = flatpak_api.get_bundle_conflict(file_path, scope_flag)
    if conflict:
        ref, origin = conflict
        output_fn(
            f"{ref} is already installed from '{origin}' — uninstalling it first (data is kept)…\n"
        )
        if _stream(flatpak_api.get_uninstall_ref_call(ref, scope_flag), output_fn) != 0:
            output_fn("Uninstall failed — bundle not installed\n")
            return False

    if _stream(flatpak_api.get_install_bundle_call(file_path, scope_flag), output_fn) == 0:
        return True

    if conflict:
        output_fn(f"Bundle install failed — reinstalling {ref} from '{origin}'…\n")
        _stream(flatpak_api.get_install_ref_call(origin, ref, scope_flag), output_fn)
    return False


def install_latest_forge_flatpak(project_url: str, scope_flag: str, output_fn) -> bool:
    """Download the latest .flatpak release asset of a GitHub/GitLab/Codeberg
    project and install it as a bundle. Blocking — call from a thread.
    `output_fn(line)` receives log lines (called from that thread).
    Never raises: any error is logged and reported as a failure."""
    tmp_dir = None
    try:
        parsed = parse_forge_url(project_url)
        if not parsed:
            output_fn(f"Unsupported project URL: {project_url}\n")
            return False
        forge_api, owner, repo = parsed

        release_info = forge_api.get_latest_release_flatpak_asset(owner, repo)
        if not release_info:
            output_fn(f"No .flatpak release found for {owner}/{repo}\n")
            return False

        # Must live under the cache dir (bind-mounted to the same host path),
        # not /tmp: when running as a Flatpak, /tmp is a private sandbox tmpfs
        # invisible to `flatpak install` run on the host via flatpak-spawn --host.
        downloads_dir = os.path.join(GLib.get_user_cache_dir(), "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(dir=downloads_dir)
        tmp_path = os.path.join(tmp_dir, release_info["asset_name"])

        output_fn(
            f"Downloading {release_info['asset_name']} from {forge_api.NAME} {owner}/{repo}…\n"
        )
        if not forge_api.download_asset(release_info["download_url"], tmp_path):
            output_fn("Download failed\n")
            return False

        flatpak_api = FlatpakApi()
        if not install_bundle(tmp_path, scope_flag, output_fn, flatpak_api):
            return False

        bundle_info = flatpak_api.get_flatpak_bundle_info(tmp_path)
        app_id = bundle_info.get("name") or f"{owner}/{repo}"
        LocalAppsRepository().insert_or_update(
            app_id, repo, forge_api.project_url(owner, repo), release_info["tag_name"]
        )
        return True
    except Exception as e:
        output_fn(f"Error: {e}\n")
        return False
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
