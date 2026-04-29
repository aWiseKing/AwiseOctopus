# Flutter Client

`flutter_client/` 是 AwiseOctopus 的 Flutter 桌面客户端壳工程。

当前阶段包含：
- 桌面工作台界面
- 客户端版本 Agent 状态编排层
- 与 Python Agent 对齐的接口契约 DTO
- Mock API 与演示场景
- 未来远程 API 适配占位

当前不包含：
- Python HTTP/WebSocket 服务实现
- 真实桌面 runner 生成文件（本机缺少 Flutter SDK，需后续执行 `flutter create . --platforms=windows,linux,macos` 补齐）

推荐后续命令：

```bash
flutter pub get
flutter create . --platforms=windows,linux,macos
flutter test
flutter run -d windows
```
