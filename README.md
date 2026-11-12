# SafePlay Companion

[راهنمای فارسی](README.fa) (open `README.fa` with Notepad if Windows asks which app to use)

SafePlay Companion is a Windows desktop helper for mpv. It reads the current file and playback position through mpv JSON IPC, obtains parental guide data from DoesTheDogDie, then looks for timestamped intervals from CleanStream/VideoSkip and CringeMDb. It seeks past selected intervals after movie-edition confirmation. It never examines video or audio and does not alter Syncplay.

**Prebuilt Windows app:** Extract `SafePlay-Companion-Windows.zip` and run `SafePlayCompanion.exe`. The current build is a single file; keep it wherever you want. The older folder build under `dist\SafePlayCompanion\` works only when its `_internal` folder stays beside the EXE.

## First use: follow these steps in order

1. **Make mpv reachable.** Close mpv and Syncplay. Open `%APPDATA%\mpv\mpv.conf` in Notepad (create the `mpv` folder and file if needed). Add this line, save, then restart mpv or Syncplay:

   ```text
   input-ipc-server=\\.\pipe\safeplay-mpv
   ```

   If your mpv installation has a `portable_config` folder beside `mpv.exe`, edit `portable_config\mpv.conf` instead. In SafePlay Settings, keep **mpv IPC pipe** at the matching default `\\.\pipe\safeplay-mpv` and click **Save settings**. You can also launch mpv with `--input-ipc-server=\\.\pipe\safeplay-mpv` instead of editing a file. Restart the actual mpv process after adding the option. **Syncplay can override the pipe from mpv.conf**; SafePlay now looks for a reachable `syncplay-mpv-*` pipe automatically. If the dashboard reports access denied, run SafePlay and Syncplay at the same Windows privilege level, or configure a shared pipe in Syncplay's Player Arguments and enter that exact pipe in SafePlay Settings. Only one mpv process can use a given pipe name. See the [mpv manual](https://mpv.io/manual/stable/) and [Syncplay IPC discussion](https://github.com/Syncplay/syncplay/issues/529).
2. **Get an API key.** Create a DoesTheDogDie API key on its [API page](https://www.doesthedogdie.com/api/3.0). In SafePlay, open **Settings**, paste it into **DoesTheDogDie API key (session only)**, and click **Save settings**. If the movie is already playing, go to **Dashboard** and click **Find guide**. The key is forgotten when you close SafePlay. To provide it automatically on later launches, set the Windows environment variable `SAFEPLAY_DDD_API_KEY` before starting the app.
3. **Play a movie in mpv.** You may start it directly or through Syncplay. Open SafePlay. **Dashboard** should say `Connected to mpv` and show the movie and playback time. SafePlay guesses the title and year from the filename; correct either field and click **Find guide** if the guess is wrong. If several matches appear, select the exact movie and year.
4. **Inspect the guide.** Open **Scenes**. If the main guide has missing times, the app checks CleanStream/VideoSkip and CringeMDb for additional start/end intervals. Wait for the scene count to update. Choose individual rows with **Skip this scene**. `Missing` means that original row has no usable interval; a matching fallback interval appears as a separate row labeled `provided`. It can skip after edition confirmation. It may be unverified or offset for another cut, so check the runtime and scene positions before enabling it. Manual editing remains available when no source covers the movie.
5. **Confirm the edition.** On **Dashboard**, click **Review and confirm movie edition**. Enter a known reference runtime in minutes, or `0` if unknown. Compare the displayed file name, title, year, runtime and scene times, then choose **Yes** only for the correct cut. The API does not provide a comparable edition runtime, so an unknown reference runtime leaves an uncertainty warning.
6. **Turn on the filters you want.** Check any of the four category boxes on **Dashboard**. **Enable all content filters** checks or clears all four. Then open **Settings**, check **Automatic skipping**, and click **Save settings**. Dashboard displays `ON` with the remaining requirement until an eligible scene is ready. **Ready now?** becomes `Yes` only for checked scenes with valid, confirmed times in enabled categories. Watch **Activity** for seek entries.

Skipping starts **OFF**. A category checkbox alone does not start skipping. Every new movie file needs its own guide and edition confirmation.

## What each screen does

### Dashboard

- **mpv status** reports whether SafePlay can talk to mpv. `Disconnected` usually means mpv is closed or its IPC pipe is missing or different. `Connected` with **no media loaded** means mpv is open but has no movie.
- **Movie**, **Playback**, **Guide**, and **Automatic skipping** show the detected title/year, current time and total duration, guide state, and whether skipping is active. `SUSPENDED` means an external playback correction was detected; review the situation and confirm the edition again before resuming.
- **Movie title**, **Year**, and **Find guide** let you correct a filename guess and search again. `Year unknown` means no year was found.
- **Review and confirm movie edition** is the safety gate for skipping. It does not edit the guide or change playback by itself.
- The four **content filter** checkboxes choose which kinds of scene may be skipped: sexual content/nudity, violence/gore, profanity/language, and drugs/alcohol. They take effect immediately; **Enable all content filters** changes all four.

### Scenes

- **Start** and **End** show the interval in `HH:MM:SS`, or `Missing` when no time was supplied. **End** is the safe-resume point. **Skip this scene** is your individual on/off choice; **Ready now?** shows whether all requirements for that row are met.
- Select a row and click **Edit selected scene** to change start/end times (entered as seconds), category, and its enabled state. Confirming an edited, valid interval marks it `manual`. Check these times against the *exact file playing*, because different cuts can have different timing.
- **Add manual scene** creates a new interval when none of the connected guides has a timestamp for a scene. It is optional.
- `Ready now? No` can mean automatic skipping is off, the edition is unconfirmed, the category or row is off, the playback duration is unavailable, or the time is missing, unreviewed, or outside the movie runtime.

### Settings

- **mpv IPC pipe:** Must equal the pipe configured in the mpv process, normally `\\.\pipe\safeplay-mpv`.
- **DoesTheDogDie API key (session only):** Credential for guide searches. It is not saved in SQLite. After entering a key while a movie is already loaded, click **Find guide** on Dashboard.
- **Connect automatically:** When checked, SafePlay repeatedly tries to connect to mpv. Turning it off disconnects; check it and save again to reconnect. There is no separate Connect button.
- **Automatic skipping:** Master on/off control. Requires a loaded guide, edition confirmation, selected categories, and eligible scene intervals. Click **Save settings** after changing it.
- **Safety margin (seconds):** From `0` to `5`; SafePlay may trigger slightly before the scene start and resumes slightly after its end. Default is `0.5` second.
- **Language:** The current app interface supports English only. The [Persian guide](README.fa) translates these instructions, not the buttons.
- **Startup window:** `Normal window` or `Minimized` controls how the app window opens. It does **not** make SafePlay start with Windows.
- **Save settings:** Applies and stores the settings above except the API key, which stays in memory only.

### Activity

Shows connection changes, movie detection, guide retrieval, edited scenes, automatic skips, and errors. **Refresh log** reloads the saved entries. Read this tab when a guide is unavailable or a skip does not happen.

## If something does not work

- **`Disconnected` or no movie:** Restart the mpv instance that plays the video after setting IPC; an already running mpv will not pick up a newly created `mpv.conf`. SafePlay also discovers Syncplay pipes. If it reports **access denied**, run the programs at the same Windows privilege level or set a shared IPC pipe in Syncplay Player Arguments. A running Syncplay window alone is not enough.
- **`API key required`, `Guide: unavailable`, or no match:** Enter your key; click **Find guide** after pasting it; check title/year and network access. Look at **Activity** for authentication, timeout, or rate-limit errors. No key means no online guide.
- **Scenes empty or all `Ready now? No`:** Wait for the external timestamp lookup to finish, then check **Activity**. If no matching source has intervals, SafePlay cannot skip that movie automatically. `Missing` means there is no time to use. If intervals are present, check the scene checkbox, category filter, edition confirmation, and Settings master switch. SafePlay never invents missing times.
- **`SUSPENDED` during Syncplay:** Another controller may have reversed a seek. Check the viewing room and editions, then reconfirm. External mpv seeks are not guaranteed to synchronize in every Syncplay setup.

## Requirements and installation

1. For the **prebuilt EXE**, install mpv and optionally Syncplay; Python is not needed. To run from **source**, install Python 3.12 or newer and, in PowerShell in this project directory, run `py -3.12 -m venv .venv`, `.venv\Scripts\Activate.ps1`, and `python -m pip install -r requirements.txt`.
2. Create your own [DoesTheDogDie API key](https://www.doesthedogdie.com/api/3.0) and accept its [API terms](https://www.doesthedogdie.com/api/terms). Set `SAFEPLAY_DDD_API_KEY` in your environment, or paste the key into Settings for the current session. The key is never written to SQLite or source files. The provider uses `X-API-KEY`.
3. Enable mpv IPC with `--input-ipc-server=\\.\pipe\safeplay-mpv`, or add `input-ipc-server=\\.\pipe\safeplay-mpv` to `mpv.conf`, then restart mpv. The path in Settings must match. Syncplay may override the config option; SafePlay searches for Syncplay's pipe or you can set the shared pipe in Syncplay Player Arguments.
4. Run `SafePlayCompanion.exe`, or `python main.py` when using the source. SafePlay connects and reconnects automatically. It identifies a title and year from the file name, searches the guide, and asks you to choose if the match is ambiguous. You can correct the title and year in Dashboard.
5. Review the Scenes tab. Edit and confirm any community interval against the exact file before use. Confirm the movie edition on Dashboard, enable the desired categories, then enable automatic skipping in Settings. Automatic skipping starts OFF.

The SQLite database and logs live at `%LOCALAPPDATA%\SafePlayCompanion\safeplay.db`. API guide cache expires after 29 days; manual edits remain when guide data refreshes. Close SafePlay to release the database. See [PRIVACY.md](PRIVACY.md) for local data handling and deletion. The API provider makes at most about 27 requests/minute and surfaces rate limit errors without automatic retry loops.

## Timestamp safety

DoesTheDogDie v3 returns `position1/2/3` and `safePosition1/2/3` on some ratings. Its community intervals still require manual review before skipping. Verified `isSceneAlert` intervals can skip after movie-edition confirmation. CleanStream/VideoSkip and CringeMDb publish start/end intervals; SafePlay labels these `provided` and lets you select them after edition confirmation. These community intervals are not guaranteed accurate. CringeMDb's guide can indicate a reference release runtime; SafePlay blocks those intervals when the playing file differs by more than two minutes. Missing or invalid times never skip. Different cuts may still drift even with similar runtimes.

Topic categories are mapped conservatively into four filters. Ambiguous or unrelated topic categories are ignored by the skipping engine. The exact phrase [Powered by DoesTheDogDie.com](https://www.doesthedogdie.com) appears wherever provider data is displayed, as required by the API terms. Free-tier API use is restricted to non-commercial use. See the linked terms for licensing, privacy, caching, and redistribution obligations before distributing an app that uses the API.

## Syncplay compatibility

Syncplay says that seeks made in its managed player can be relayed to participants. SafePlay issues seek commands directly to **mpv**, never to Syncplay, and cannot tell whether a specific room accepts, broadcasts, or reverts them. Its duplicate-skip guard and post-seek correction detector reduce loops; a correction suspends further skipping until you reconfirm. A managed room may block a participant's seek. Multiple participants running SafePlay with different categories or different movie editions can diverge or repeatedly correct each other. For synchronized filtered playback, use identical files/editions, guide data, filters, and SafePlay settings, and test the room together. A single designated participant driving seeks may be preferable if Syncplay relays that participant's seeks. This behavior has **not** been verified in a live Syncplay session in this project.

Suggested live test: start two Syncplay clients in one room with the same test video and an mpv IPC pipe for each client; use a manually reviewed short interval, enable skipping on one participant, and check the other participant's position and the Syncplay log. Repeat in a managed room and with both participants running identical filters. Stop if a seek is reverted or oscillates.

## Build and test

Run `python -m pytest -q` for isolated engine, cache, provider normalization, and mock IPC tests. No real movie, API credential, mpv process, or Syncplay server is needed for tests. For a Windows distribution run `./build.ps1` with Python 3.12+. The standalone executable appears at `dist\SafePlayCompanion.exe` and can be copied by itself. The optional folder build (`build/SafePlay.spec`) requires its entire `dist\SafePlayCompanion` folder, including `_internal`; running that EXE alone causes missing Qt DLL errors. The icon in `assets` is a placeholder.

## Limitations

The app currently offers an English interface. An API key is needed for DoesTheDogDie searches. CleanStream is read from its public JSON catalog; CringeMDb intervals are read from its public movie guide pages. Source availability and coverage can change. The app does no video analysis. A live Syncplay seek has not been verified on this machine because the current Syncplay pipe denies access.

Official references: [DoesTheDogDie API v3](https://www.doesthedogdie.com/api/3.0), [API terms](https://www.doesthedogdie.com/api/terms), [mpv manual](https://mpv.io/manual/stable/), [Syncplay](https://github.com/Syncplay/syncplay).
