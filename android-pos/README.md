# Ghazala POS Android

Dedicated Android shell for the Ghazala POS portal.

## Test flow

1. Run Ghazala backend on the PC so it is reachable on the local network.
2. Put the PC and POS machine on the same Wi-Fi/LAN.
3. Install the debug APK on the POS machine.
4. On first launch, enter the PC URL, for example:
   `http://192.168.1.25:8000/`
5. The app opens the same universal Ghazala login page.
6. Login with a POS account such as `pos.jeddah`.
7. Existing web routing sends the user to `/pos`.
8. Create shipment, print/reprint, records, settings and dispatch all use the central backend/database.

## Change server URL

Long-press anywhere in the app to reopen the server URL dialog. This allows local testing when the PC IP changes without rebuilding the APK.

## Printing

The JavaScript bridge is exposed as `window.GhazalaPOSPrinter`.

The first test build uses Android's system print framework as a fallback. Direct printing to the integrated thermal printer requires the exact POS manufacturer/model printer SDK or Android service/AIDL contract. Once that SDK is supplied, the bridge methods can be wired to it without changing the web POS workflow.

## Build

Open `android-pos` in Android Studio and build the debug APK, or use the included GitHub Actions workflow.
