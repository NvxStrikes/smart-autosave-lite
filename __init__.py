bl_info = {
    "name": "Smart AutoSave+ Lite — by NovaStrikes",
    "author": "Hamayl Shahbaz (NovaStrikes)",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Smart AutoSave+ Lite",
    "description": "Free lite autosave for Blender. Saves up to 3 backups on a timer. Upgrade to Pro for checkpoints, timeline, crash recovery & more.",
    "doc_url": "https://superhivemarket.com/products/autosave-pro",
    "category": "System",
}

# ─────────────────────────────────────────────────────────────────
# Smart AutoSave+ Lite — Free Version by NovaStrikes
# Upgrade to Smart AutoSave+ Pro for full features:
# → Named Checkpoints, Visual Timeline, Partial Restore,
#   Backup Health Report, Smart Triggers, Recovery Dialog & more.
# https://superhivemarket.com/products/autosave-pro
# ─────────────────────────────────────────────────────────────────

import bpy
import os
import re
import time
import platform
import subprocess
from typing import Optional, List, Tuple
from bpy.props import IntProperty, BoolProperty
from bpy.types import Panel, AddonPreferences, Operator
from bpy.app.handlers import persistent

# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

ADDON_ID        = __name__
FOLDER_NAME     = "autosaves"
MAX_BACKUPS     = 3          # Hard limit in Lite — upgrade for more
UPGRADE_URL     = "https://superhivemarket.com/products/autosave-pro"

_last_save_time: float  = 0.0
_TIMER_REGISTERED: bool = False

# ─────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────

def _get_prefs():
    pa = bpy.context.preferences.addons.get(ADDON_ID)
    return getattr(pa, "preferences", None) if pa else None


def _project_paths() -> Tuple[Optional[str], Optional[str]]:
    try:
        if not bpy.data.filepath or not os.path.exists(bpy.data.filepath):
            return None, None
        dirname = os.path.dirname(bpy.data.filepath)
        name    = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        return dirname, name
    except Exception:
        return None, None


def _autosave_dir(dirname: str) -> str:
    folder = os.path.join(dirname, FOLDER_NAME)
    os.makedirs(folder, exist_ok=True)
    return folder


def _list_backups(dirname: str) -> List[str]:
    folder = os.path.join(dirname, FOLDER_NAME)
    if not os.path.exists(folder):
        return []
    _, name = _project_paths()
    if not name:
        return []
    pattern = re.compile(
        rf"^{re.escape(name)}_Lite_Backup_(\d+)\.blend$", re.IGNORECASE
    )
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if pattern.match(f)
    ]
    files.sort(key=lambda fp: os.path.getmtime(fp), reverse=True)
    return files


def _next_save_path(dirname: str, name: str) -> str:
    folder   = _autosave_dir(dirname)
    backups  = _list_backups(dirname)
    pattern  = re.compile(
        rf"^{re.escape(name)}_Lite_Backup_(\d+)\.blend$", re.IGNORECASE
    )
    max_num  = 0
    for fp in backups:
        m = pattern.match(os.path.basename(fp))
        if m:
            try:
                max_num = max(max_num, int(m.group(1)))
            except ValueError:
                pass
    return os.path.join(folder, f"{name}_Lite_Backup_{max_num + 1}.blend")


def _prune(dirname: str, name: str):
    """Keep only the most recent MAX_BACKUPS files."""
    backups = _list_backups(dirname)          # already sorted newest → oldest
    for fp in backups[MAX_BACKUPS:]:
        try:
            os.remove(fp)
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────────
# Core autosave
# ─────────────────────────────────────────────────────────────────

def perform_autosave():
    global _last_save_time
    try:
        dirname, name = _project_paths()
        if not dirname or not name:
            return                            # file not saved yet — skip silently

        path = _next_save_path(dirname, name)
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
        _prune(dirname, name)
        _last_save_time = time.monotonic()

        # Subtle Blender status message — no popup spam
        print(f"[AutoSave+ Lite] Saved → {os.path.basename(path)}")

    except Exception as e:
        print(f"[AutoSave+ Lite] Error: {e}")


def autosave_timer():
    global _last_save_time
    try:
        prefs = _get_prefs()
        if not prefs or not getattr(prefs, "enable_autosave", True):
            return 5.0
        if not getattr(bpy.data, "is_saved", False):
            return 5.0

        interval = max(1, prefs.interval_minutes) * 60
        if _last_save_time == 0.0:
            _last_save_time = time.monotonic()
            return 5.0

        if time.monotonic() - _last_save_time >= interval:
            perform_autosave()

    except Exception as e:
        print(f"[AutoSave+ Lite] Timer error: {e}")

    return 5.0

# ─────────────────────────────────────────────────────────────────
# Handler — restart timer on file load
# ─────────────────────────────────────────────────────────────────

@persistent
def _on_load(dummy=None):
    global _last_save_time
    _last_save_time = time.monotonic()
    _register_timer()

# ─────────────────────────────────────────────────────────────────
# Timer management
# ─────────────────────────────────────────────────────────────────

def _register_timer():
    global _TIMER_REGISTERED
    if _TIMER_REGISTERED:
        return
    try:
        bpy.app.timers.register(autosave_timer, first_interval=5.0)
        _TIMER_REGISTERED = True
    except Exception:
        pass


def _unregister_timer():
    global _TIMER_REGISTERED
    try:
        if _TIMER_REGISTERED:
            bpy.app.timers.unregister(autosave_timer)
    except Exception:
        pass
    _TIMER_REGISTERED = False

# ─────────────────────────────────────────────────────────────────
# Operators
# ─────────────────────────────────────────────────────────────────

class LITE_OT_force_save(Operator):
    bl_idname  = "autosave_lite.force_save"
    bl_label   = "Save Backup Now"
    bl_description = "Immediately create a backup of your current scene"

    def execute(self, context):
        dirname, _ = _project_paths()
        if not dirname:
            self.report({'WARNING'}, "Please save your .blend file first!")
            return {'CANCELLED'}
        perform_autosave()
        self.report({'INFO'}, "Backup saved! (Lite — max 3 kept)")
        return {'FINISHED'}


class LITE_OT_open_folder(Operator):
    bl_idname  = "autosave_lite.open_folder"
    bl_label   = "Open Backup Folder"
    bl_description = "Open the autosaves folder in your file explorer"

    def execute(self, context):
        dirname, _ = _project_paths()
        if not dirname:
            self.report({'WARNING'}, "Save your .blend file first.")
            return {'CANCELLED'}
        folder = _autosave_dir(dirname)
        try:
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.call(["open", folder])
            else:
                subprocess.call(["xdg-open", folder])
        except Exception:
            self.report({'ERROR'}, "Could not open folder.")
            return {'CANCELLED'}
        return {'FINISHED'}


class LITE_OT_upgrade(Operator):
    bl_idname  = "autosave_lite.upgrade"
    bl_label   = "Upgrade to Pro →"
    bl_description = "Get Named Checkpoints, Visual Timeline, Recovery Dialog, Smart Triggers & more"

    def execute(self, context):
        bpy.ops.wm.url_open(url=UPGRADE_URL)
        return {'FINISHED'}

# ─────────────────────────────────────────────────────────────────
# Preferences
# ─────────────────────────────────────────────────────────────────

class AutoSaveLitePreferences(AddonPreferences):
    bl_idname = ADDON_ID

    enable_autosave: BoolProperty(
        name="Enable AutoSave+ Lite",
        default=True
    )
    interval_minutes: IntProperty(
        name="Save Every (minutes)",
        default=5, min=1, max=60
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Smart AutoSave+ Lite — by NovaStrikes", icon="FILE_BACKUP")
        layout.separator()

        col = layout.column()
        col.prop(self, "enable_autosave")
        col.prop(self, "interval_minutes")

        layout.separator()
        layout.label(text=f"Keeps last {MAX_BACKUPS} backups. Upgrade Pro for unlimited.", icon="INFO")
        layout.operator("autosave_lite.upgrade", icon="FUND")

# ─────────────────────────────────────────────────────────────────
# Panel
# ─────────────────────────────────────────────────────────────────

class LITE_PT_panel(Panel):
    bl_label      = "Smart AutoSave+ Lite"
    bl_idname     = "LITE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type= "UI"
    bl_category   = "Smart AutoSave+ Lite"

    def draw(self, context):
        layout = self.layout
        prefs  = _get_prefs()

        # Header
        layout.label(text="AutoSave+ Lite", icon="FILE_BACKUP")

        # Unsaved file warning
        if not getattr(bpy.data, "is_saved", False):
            layout.label(text="Save your .blend file first!", icon="ERROR")
            return

        # Status
        if prefs:
            col = layout.column()
            col.prop(prefs, "enable_autosave")
            col.prop(prefs, "interval_minutes")
            layout.separator()

            # Next save countdown
            if _last_save_time > 0.0 and prefs.enable_autosave:
                elapsed    = time.monotonic() - _last_save_time
                remaining  = max(0, prefs.interval_minutes * 60 - elapsed)
                layout.label(
                    text=f"Next save in: {int(remaining)}s",
                    icon="TIME"
                )
            else:
                layout.label(text="Timer active", icon="TIME")

        layout.separator()

        # Action buttons
        row = layout.row(align=True)
        row.operator("autosave_lite.force_save", icon="FILE_TICK")
        row.operator("autosave_lite.open_folder", icon="FILE_FOLDER")

        # Recent backups — last 3
        layout.separator()
        layout.label(text=f"Recent Backups (max {MAX_BACKUPS}):", icon="RECOVER_LAST")
        dirname, _ = _project_paths()
        if dirname:
            backups = _list_backups(dirname)
            if backups:
                for fp in backups[:MAX_BACKUPS]:
                    row  = layout.row(align=True)
                    ts   = time.strftime("%H:%M", time.localtime(os.path.getmtime(fp)))
                    name = os.path.basename(fp)
                    row.label(text=f"{name}  ({ts})")
                    op  = row.operator("wm.open_mainfile", text="", icon="RECOVER_LAST")
                    op.filepath = fp
            else:
                layout.label(text="No backups yet.", icon="INFO")

        # ── Upgrade Banner ──────────────────────────────────────────
        layout.separator()
        box = layout.box()
        box.label(text="Want more? Upgrade to Pro:", icon="FUND")
        box.label(text="✦ Named Checkpoints")
        box.label(text="✦ Visual Timeline Browser")
        box.label(text="✦ Crash Recovery Dialog")
        box.label(text="✦ Smart Triggers (FPS/Memory)")
        box.label(text="✦ Backup Health Report")
        box.operator("autosave_lite.upgrade", icon="URL")

# ─────────────────────────────────────────────────────────────────
# Register / Unregister
# ─────────────────────────────────────────────────────────────────

classes = (
    AutoSaveLitePreferences,
    LITE_PT_panel,
    LITE_OT_force_save,
    LITE_OT_open_folder,
    LITE_OT_upgrade,
)


def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except Exception:
            pass
    try:
        if _on_load not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_on_load)
    except Exception:
        pass
    _register_timer()


def unregister():
    global _last_save_time, _TIMER_REGISTERED
    _unregister_timer()
    try:
        if _on_load in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_on_load)
    except Exception:
        pass
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
    _last_save_time    = 0.0
    _TIMER_REGISTERED  = False


if __name__ == "__main__":
    register()
