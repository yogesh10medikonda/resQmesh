# ResQMesh

Offline-first disaster communication app for Android. ResQMesh lets volunteer smartphones relay emergency SOS messages device-to-device over Bluetooth when mobile networks and internet are unavailable — no infrastructure required.

## The Problem

During disasters (floods, cyclones, earthquakes, landslides), mobile networks and internet access frequently fail, cutting off communication between affected people, volunteers, and rescue teams exactly when it matters most.

## The Solution

ResQMesh turns nearby volunteer phones into a communication relay using Bluetooth and a store-and-forward mechanism:

## Status

**Core functionality tested and working** on real Android hardware, fully offline (Wi-Fi and mobile data both disabled):

- ✅ Offline SOS creation and local storage (SQLite)
- ✅ Bluetooth adapter detection and paired-device listing
- ✅ Nearby device discovery
- ✅ Real device-to-device Bluetooth transfer (RFCOMM sockets)
- ✅ Store-and-forward: batch message relay with automatic retry
- 🔜 Online sync to a backend once internet returns (Firebase)
- 🔜 Offline maps, volunteer verification, multilingual support, and more

## Tech Stack

- **App**: Python 3.12 + Kivy 2.3.1
- **Storage**: SQLite (on-device)
- **Device-to-device link**: Bluetooth Classic (RFCOMM via pyjnius)
- **Android packaging**: Buildozer + python-for-android

## Building

Requires WSL2 (or Linux/macOS) for the Android build step, since Buildozer doesn't run natively on Windows.

```bash
python3.12 -m venv buildenv
source buildenv/bin/activate
pip install buildozer "Cython<3.1"
buildozer android debug
```

## License

MIT — see [LICENSE](LICENSE).`
