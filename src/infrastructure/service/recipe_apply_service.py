import subprocess
import threading

from gi.repository import GLib

from infrastructure.api.flatpak_api import FlatpakApi
from infrastructure.service.forge_install_service import install_latest_forge_flatpak
from infrastructure.service.install_queue_service import InstallQueueService


def _stream(cmd, output_fn) -> int:
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    for line in process.stdout:
        output_fn(line)
    return process.wait()


def apply_recipe_permission_list(
    app_id: str,
    active_permission_list: list,
    scope_flag: str,
    output_fn,
    flatpak_api=None,
) -> bool:
    """Apply the permissions picked in InstallDialog to an installed app:
    `flatpak override` calls, then the extra flatpaks (plugins, Vulkan
    layers…) installed in the same `scope_flag` as the app, at the branch
    its extension points expect. Blocking — call from a thread.
    Returns False when an override or an extra install failed."""
    flatpak_api = flatpak_api or FlatpakApi()
    if active_permission_list and not flatpak_api.is_app_id_installed(app_id):
        # The app install itself failed: overrides would error out and
        # extension branches can't be resolved without the app's metadata.
        output_fn(f"{app_id} is not installed — recipe skipped\n")
        return False
    ok = True
    for perm, value in active_permission_list:
        override_call = flatpak_api.get_recipe_override_call(app_id, perm, value)
        if override_call:
            ok &= _stream(override_call, output_fn) == 0
        elif perm.is_install_flatpak_yes_no():
            ref = flatpak_api.get_extension_ref(app_id, perm.get_value())
            if flatpak_api.is_ref_installed(ref):
                output_fn(f"{ref} is already installed\n")
                continue
            ok &= _stream(flatpak_api.get_install_call(ref, "flathub", scope_flag), output_fn) == 0
        elif perm.is_install_forge_flatpak_yes_no():
            ok &= install_latest_forge_flatpak(perm.get_value(), scope_flag, output_fn)
    return ok


def apply_recipe_overrides_async(app_id: str, app_name: str, active_permission_list: list):
    """Apply the "Recipe overrides" dialog of an already installed app. Overrides run
    silently; when the recipe also installs extra flatpaks, they are
    tracked in the Pending page like any install."""
    flatpak_api = FlatpakApi()
    scope = flatpak_api.get_installation_scope(app_id)
    queue_item = None
    if any(perm.is_install_yes_no() for perm, _value in active_permission_list):
        queue_item = InstallQueueService().enqueue(
            app_id, app_name, scope, show_output_default=True
        )

    def run():
        output_fn = (
            (lambda line: GLib.idle_add(queue_item.append_output, line))
            if queue_item
            else (lambda _line: None)
        )
        ok = apply_recipe_permission_list(
            app_id, active_permission_list, f"--{scope}", output_fn, flatpak_api
        )
        if queue_item:
            GLib.idle_add(queue_item.set_status, "done" if ok else "failed")

    threading.Thread(target=run, daemon=True).start()
