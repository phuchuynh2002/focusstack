# Cập nhật 0.3

Desktop hiện nhận RAW trực tiếp. RAW được phát triển cục bộ sang sRGB và không áp dụng chỉnh sửa Capture One; xuất TIFF 16-bit cùng ICC nếu cần giữ chỉnh sửa. Các mô tả 0.2 bên dưới là lịch sử.

# Capture One integration status

This is an independent desktop preview, not an approved Capture One plugin.
Installed version observed on this development Mac: 16.9.0.10.

## Available now

- Standalone PySide6 UI, file/folder drop, checkable source list, source/result preview with zoom/pan.
- Method A with isolated worker process and cancellation; temporary results are separate from sources.
- TIFF output preserves a shared input ICC profile. Different profiles (including tagged vs untagged) are rejected. No profile conversion is performed. Export all source variants using the same ICC profile, dimensions and bit depth.
- The macOS app declares TIFF/JPEG/PNG and camera RAW document handling and accepts Qt FileOpen events; command-line arguments accept multiple paths. Accepted RAW extensions are listed in README.md. This is the app-side entry point for external editing, not a Capture One SDK plugin.
- Direct RAW input uses LibRaw development, not Capture One adjustments. Use exported 16-bit TIFFs when Capture One's rendering must be retained. RAW output is not supported; stack results are RGB TIFFs.

## Manual compatibility test (not yet performed in Capture One)

1. Export 3–10 variants of the same scene from Capture One as RGB TIFF 16-bit, same ICC, full size. Avoid varying crop, rotation, WB or exposure.
2. Open the app and add all exported TIFFs. They must appear in one stack. Run Stack, inspect at 100%, save to a new TIFF filename.
3. Import that new file into the original Session/Catalog. Confirm orientation, dimensions, ICC and neutral patch colors. Do not assume Edit With automatically imports a newly named many-to-one result.
4. After installing the app, test whether Edit With/Open With offers it on the installed Capture One version. Test both app-not-running and app-already-running with multiple images. Do not claim this route supported until the test passes.
5. Repeat with spaces/Unicode in filenames, cancellation, corrupt input and different ICC profiles.

## Official plugin and vendor confirmation — outstanding

The official [Developer Portal](https://www.captureone.com/en/partnerships/developer) provides developer signup, SDK documentation/sample projects for macOS and Windows, and a plugin submission route. The [plugin page](https://www.captureone.com/en/partnerships/plug-ins) links the developer program.

Next prerequisites: obtain the official SDK and its terms through the developer account; implement the native adapter against the actual supported export/import lifecycle; test round-trip with Sessions and Catalogs; prepare build, compatibility matrix, reproduction steps, logs and support details for vendor review. The public portal does not promise certification or acceptance. Written vendor confirmation is required before claiming approval. No SDK headers, fake plugin manifest, vendor signature or approval is included here. No application or email has been sent to Capture One.

macOS Developer ID signing/notarization is a separate distribution requirement from Capture One approval. This local build is for testing and is not Developer ID signed/notarized. Build Windows on Windows; a macOS build does not produce a tested Windows executable.

## Desktop 0.2 workflow update

The desktop now requires rendered RGB 16-bit TIFFs with an embedded shared ICC profile before scanning/stacking. Incoming RAW files are skipped with a log message and are not decoded by the GUI; conversion happens before import in Capture One. This preserves the supplied rendered TIFF pixels and profile; it cannot recover Capture One edits from RAW or certify that an arbitrary TIFF was rendered by Capture One.

The file count distinguishes received files, checked inputs and the current preview. macOS FileOpen events are batched and deduplicated; files arriving while processing are queued explicitly. If Capture One sends only one variant, check **Image → Edit All Selected Variants**. [Capture One selection guidance](https://support.captureone.com/hc/en-us/articles/360002480877-Adjusting-multiple-images-at-a-time).

Progress, thumbnails, focus maps, verified TIFF reports and local provenance are described in [desktop workflow](desktop.md). Native SDK integration, automatic Capture One rendering/import and AI analysis are not implemented. No customer image is uploaded by this workflow.
