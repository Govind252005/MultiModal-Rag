// ============================================================================
// shortcuts.iss
// ----------------------------------------------------------------------------
// Creates desktop and Start Menu shortcuts. Actual [Icons] entries live in
// installer.iss (Inno requires them declared in the section, not procedurally
// in most cases); this module provides the procedural fallback used when a
// shortcut needs to be (re)created post-install, e.g. after a repair.
// ============================================================================

#ifndef SHORTCUTS_ISS
#define SHORTCUTS_ISS

procedure CreateDesktopShortcut();
var
  ShortcutPath, TargetPath, IconPath, WorkingDir: String;
begin
  ShortcutPath := ExpandConstant('{userdesktop}\{#APP_NAME}.lnk');
  TargetPath := ExpandConstant('{app}\{#APP_EXE_NAME}');
  IconPath := ExpandConstant('{app}\{#APP_EXE_NAME}');
  WorkingDir := ExpandConstant('{app}');

  if FileExistsSafe(TargetPath) then
  begin
    CreateShellLink(ShortcutPath, '{#APP_NAME}', TargetPath, '', WorkingDir, IconPath, 0, SW_SHOWNORMAL);
    LogSuccess('Desktop shortcut created: ' + ShortcutPath);
  end
  else
    LogWarning('Could not create desktop shortcut: target executable not found.');
end;

procedure CreateStartMenuShortcut();
var
  GroupDir, ShortcutPath, TargetPath, IconPath, WorkingDir: String;
begin
  GroupDir := ExpandConstant('{group}');
  EnsureDirectory(GroupDir);

  ShortcutPath := GroupDir + '\{#APP_NAME}.lnk';
  TargetPath := ExpandConstant('{app}\{#APP_EXE_NAME}');
  IconPath := ExpandConstant('{app}\{#APP_EXE_NAME}');
  WorkingDir := ExpandConstant('{app}');

  if FileExistsSafe(TargetPath) then
  begin
    CreateShellLink(ShortcutPath, '{#APP_NAME}', TargetPath, '', WorkingDir, IconPath, 0, SW_SHOWNORMAL);
    LogSuccess('Start Menu shortcut created: ' + ShortcutPath);
  end
  else
    LogWarning('Could not create Start Menu shortcut: target executable not found.');

  // Uninstall shortcut
  CreateShellLink(GroupDir + '\Uninstall {#APP_NAME}.lnk', 'Uninstall {#APP_NAME}',
    ExpandConstant('{uninstallexe}'), '', ExpandConstant('{app}'), '', 0, SW_SHOWNORMAL);
end;

#endif
