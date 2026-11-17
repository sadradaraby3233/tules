# TULES for Android (early companion)

A separate Kotlin/Jetpack Compose app for a human-in-the-loop clipboard workflow. It does
not connect to an AI service. It supports a **subset** of the desktop protocol, not the
Python application or browser automation.

## Build and install

Open `android/` in Android Studio (JDK 17, Android SDK 35, Gradle 8.9), sync, then run
on a device or emulator with Android 8.0/API 26 or later. Alternatively, with Gradle 8.9
installed, run `gradle :app:assembleDebug :app:testDebugUnitTest` from `android/`.
The debug APK is `app/build/outputs/apk/debug/app-debug.apk`. SDK and Gradle dependencies
must be downloaded from Google's Maven repository, Maven Central and the Gradle plugin
portal. This repository does not include a Gradle wrapper or a prebuilt APK.

## Use

1. Open TULES and choose a project folder through Android's system folder picker. The
   app requests persistent read/write access to that folder. Providers and Android may
   restrict access to some locations (such as Android/data and the storage root).
2. Tap **Copy setup prompt** and paste it into your AI chat. Give the AI your task.
3. Copy its response, return to TULES, tap **Load clipboard**, review the editable
   command, and tap **Run reviewed command**. Then tap **Copy result** and paste it
   back into the chat. Repeating a command can repeat its edits; always review it.
4. For a quicker return, edit the Android Quick Settings panel and add the **TULES**
   tile. It opens the app; it does not read the clipboard or run anything itself.

**Why not automatic background monitoring?** On Android 10 and newer, ordinary
background apps generally cannot read the clipboard unless they are the focused app
or the default keyboard. A foreground service alone does not bypass that restriction.
This app reads it only when you explicitly tap Load while TULES is in the foreground.
There is no accessibility service, overlay, keyboard replacement, or unattended agent.

## Commands and safety

Use `edit: {"action":"help"} endedit` for the built-in command list. The initial
subset implements `help`, `list_actions`, `list_files`, `read`/`read_file`/`view`,
`search`, exact `replace`, `write`, `create_file`, and `undo`. Commands accept JSON objects or arrays; batches execute
sequentially and do not roll back on failure. No shell, internet tools, regex/fuzzy
replacement, automatic review, or Python syntax checking are included. JSON files get
a best-effort parse check, not schema validation. Always review the resulting files
and run your project's own tests using another tool.

Paths are relative to the selected tree; `..`, absolute paths, and backslashes are
rejected. Scans skip hidden names and common generated directories, cap the workspace at
500 files/2,000 entries, and reject files larger than 1 MiB. Direct reads can still access
hidden files; don't grant access to a folder containing secrets you don't want to share.
Parent directories must already exist when writing or creating files. UTF-8 text only. A read window returns a continuation when more lines remain. Search is a
case-insensitive literal search, returns at most 100 results, and reports unreadable files.

Before overwriting, the app stores one private backup per tree and path; `undo` restores it.
Backups are lost if the app is uninstalled or its data is cleared, and newly created
files have no undo. External changes may make a backup stale; inspect before restoring. Use version control or your own backups. Document providers vary:
writes are **not atomic**, and a failed write or restore may leave partial contents. The
app checks the written bytes and retains the backup, but cannot guarantee recovery if the
provider fails. The app does not protect against another process changing files at the
same time. Select trusted folders, inspect the output, and do not treat this as a sandbox.

## Manual device checks

After building, test on a real device and on an emulator: grant a test folder, restart
the app to check the persisted grant, copy and run a read/replace/undo round trip, and
add the Quick Settings tile. Try a cancelled picker, an unavailable/revoked provider,
a duplicate replacement, a non-UTF-8 file, and an oversized file. Check provider write
behavior on both local storage and any cloud provider you intend to use.
