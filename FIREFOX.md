# Port Firefox

Repo này có 3 WebExtension có thể load trực tiếp trong Firefox:

- `open-with-mpv`
- `yt-minimalist`
- `remap-copy-paste`

## Load tạm thời để test

1. Mở `about:debugging#/runtime/this-firefox`.
2. Chọn **Load Temporary Add-on...**.
3. Chọn file `manifest.json` trong từng thư mục extension.

## `open-with-mpv`: native messaging

Firefox native messaging cần host manifest dùng `allowed_extensions`, nên extension này có ID Gecko cố định là `open-with-mpv@local`.

### Cài native host

Cài host manifest cho user hiện tại trên Linux:

```bash
./open-with-mpv/install-firefox-native-host.sh
```

Script sẽ tạo:

```text
~/.mozilla/native-messaging-hosts/com.hau.mpv.json
```

`yt_mpv.py` vẫn cần các lệnh hệ thống mà script đang gọi được cài sẵn, gồm `python3`, `mpv`, `socat`, `kitty`, và `bash`.

Sau khi cài native host:

1. Mở `about:debugging#/runtime/this-firefox`.
2. Load `open-with-mpv/manifest.json`.
3. Mở một video YouTube.
4. Click icon extension hoặc chuột phải và chọn menu MPV.

Nếu báo lỗi native host, kiểm tra file host Firefox:

```bash
cat ~/.mozilla/native-messaging-hosts/com.hau.mpv.json
```

Các điểm phải khớp:

- `name` là `com.hau.mpv`, giống `HOST_NAME` trong `open-with-mpv/background.js`.
- `path` là đường dẫn tuyệt đối tới `open-with-mpv/yt_mpv.py`.
- `allowed_extensions` có `open-with-mpv@local`, giống `browser_specific_settings.gecko.id` trong manifest extension.
- `yt_mpv.py` có quyền execute.

## Đóng gói add-on

Firefox nhận file `.zip`/`.xpi`, nhưng để cài lâu dài trên Firefox Release/Beta thì add-on phải được Mozilla ký.

Đóng gói thủ công từng extension:

```bash
cd open-with-mpv
zip -r ../open-with-mpv.zip . -x "payload.bin" "mpv_debug.log" "__pycache__/*" "*.pyc"

cd ../yt-minimalist
zip -r ../yt-minimalist.zip . -x "_metadata/*"

cd ../remap-copy-paste
zip -r ../remap-copy-paste.zip .
```

Hoặc dùng `web-ext` nếu đã cài:

```bash
web-ext build --source-dir open-with-mpv --artifacts-dir dist --ignore-files yt_mpv.py com.hau.mpv.firefox.json install-firefox-native-host.sh test.json payload.bin mpv_debug.log __pycache__ '*.pyc'
web-ext build --source-dir yt-minimalist --artifacts-dir dist --ignore-files _metadata
web-ext build --source-dir remap-copy-paste --artifacts-dir dist
```

## Ký add-on

Tạo API key trên AMO:

1. Đăng nhập `https://addons.mozilla.org/`.
2. Mở trang developer/API keys.
3. Tạo JWT issuer và secret.

Cài `web-ext`:

```bash
npm install --global web-ext
```

Ký để tự phân phối, không public trên AMO:

```bash
web-ext sign \
  --source-dir open-with-mpv \
  --artifacts-dir dist \
  --channel unlisted \
  --api-key "$AMO_JWT_ISSUER" \
  --api-secret "$AMO_JWT_SECRET" \
  --ignore-files yt_mpv.py com.hau.mpv.firefox.json install-firefox-native-host.sh test.json payload.bin mpv_debug.log __pycache__ '*.pyc'
```

Làm tương tự cho hai extension còn lại:

```bash
web-ext sign --source-dir yt-minimalist --artifacts-dir dist --channel unlisted --api-key "$AMO_JWT_ISSUER" --api-secret "$AMO_JWT_SECRET" --ignore-files _metadata
web-ext sign --source-dir remap-copy-paste --artifacts-dir dist --channel unlisted --api-key "$AMO_JWT_ISSUER" --api-secret "$AMO_JWT_SECRET"
```

File `.xpi` đã ký sẽ nằm trong `dist/`.

Muốn publish public trên AMO thì dùng `--channel listed` và đi qua review/public listing của AMO.

## Ghi chú tương thích

- Cả 3 manifest đã có `browser_specific_settings.gecko.id`; Chromium sẽ bỏ qua khóa này.
- Các extension có background đang dùng `background.scripts` cho Firefox, vì `background.service_worker` có thể bị tắt trong một số bản/cấu hình Firefox.
- `yt-minimalist` vẫn dùng Manifest V3 `declarativeNetRequest`, nên cần Firefox bản mới đủ hỗ trợ MV3/DNR.
- Manifest đang đặt `strict_min_version` là `142.0` để tương thích với `data_collection_permissions` khi submit/ký add-on mới.
- Khi đóng/mở lại Firefox, extension load tạm thời sẽ mất. Để dùng lâu dài trên Firefox Release/Beta cần đóng gói và ký add-on.
- Native messaging host không được đóng gói/cài tự động bởi `.xpi`; người dùng vẫn phải cài native host manifest riêng trên máy.
