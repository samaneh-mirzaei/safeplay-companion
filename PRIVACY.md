# SafePlay Companion privacy notice

SafePlay Companion runs locally. It reads the media path, playback position, duration, and pause state from a local mpv named pipe. It stores movie titles, external IDs, guide intervals, your edits and settings, and activity logs in `%LOCALAPPDATA%\SafePlayCompanion\safeplay.db` on your computer. It does not upload playback logs or scan the media file.

When you request a guide, SafePlay sends the title and optional release year to the DoesTheDogDie API. Requests include the API key you provide. DoesTheDogDie processes those requests under its own [privacy policy](https://www.doesthedogdie.com/privacy) and [API terms](https://www.doesthedogdie.com/api/terms). SafePlay keeps the API key in memory for the current session or reads it from `SAFEPLAY_DDD_API_KEY`; it does not save the key in its database.

The app does not include telemetry or an online account. It retains local activity logs and your edits until you remove the database. Cached API guides expire after 29 days and are purged on the next app launch or cache lookup. To erase all local SafePlay data, close the app and delete `%LOCALAPPDATA%\SafePlayCompanion\safeplay.db` and its optional `-wal` and `-shm` files.

This notice is a project file. Anyone distributing an API-enabled build should publish an accessible version of the notice and check the current API terms and applicable privacy requirements.
