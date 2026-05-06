# Live2D 运行后不显示修复计划

## 目标

修复 Flutter 桌面项目运行后 Live2D 桌宠不显示的问题，确保启动后能够正常看到桌宠窗口，并且能够完成模型加载、WebView 渲染和窗口显示流程。

## 现状判断

根据现有代码，Live2D 显示链路大致是：
1. `main.dart` 解析启动参数并初始化桌面窗口。
2. 主窗口通过 `AppWindowBootstrap` 初始化 Live2D 控制器。
3. 桌宠窗口通过 `Live2dPetWindow` 加载本地 HTTP 资源页。
4. WebView 访问 `assets/live2d/viewer/index.html`，再由 JS 拉起 Cubism 模型。

桌宠不显示的可能原因包括：
- 桌宠窗口未被创建或未被 show。
- 主窗口与桌宠窗口的启动角色判断不一致。
- Windows/macOS 的 WebView 初始化或插件注册不完整。
- 本地资源服务器路径映射不正确，导致 viewer 页面或模型资源 404。
- `Live2D` 页面虽然打开，但模型初始化失败，页面为空白。
- 启动后默认只显示主窗口，没有触发桌宠显示逻辑。

## 实施步骤

### 1. 追踪启动链路
- 检查 `lib/main.dart`、`lib/app/window_bootstrap.dart`、`lib/app/window_role.dart` 的启动参数解析与窗口角色分发。
- 确认运行主程序时，桌宠窗口是否被主动创建。
- 检查自启动与非自启动分支是否都会进入桌宠显示流程。

### 2. 检查桌宠窗口创建与显示逻辑
- 审核 `Live2dPetController.ensurePetWindowVisible()`、`initializeMainWindow()`、`initializePetWindow()` 的调用顺序。
- 确认窗口创建后是否正确 `show()`，以及是否被错误地隐藏或提前关闭。
- 检查主窗口关闭拦截与桌宠显示策略是否冲突。

### 3. 检查资源服务器与网页加载
- 审核 `Live2dAssetServer` 的路径映射规则，确认 `viewer/index.html`、`live2d_bootstrap.js`、`live2d_bridge.js` 和模型资源路径都能正确命中。
- 检查 `assets` 声明是否与实际资源目录一致。
- 确认 WebView 打开的是可访问的本地地址，而不是错误的相对路径。

### 4. 检查 WebView 和平台插件
- 检查 Windows 与 macOS 的 WebView 初始化分支是否都能成功执行。
- 确认平台插件已正确注册，尤其是桌宠窗口所在的多窗口回调。
- 如果 WebView2 Runtime 缺失或初始化失败，补充更明确的状态提示，避免页面看起来像“没有显示”。

### 5. 补强可见性与错误反馈
- 在桌宠窗口中增加更明确的加载态和错误态呈现。
- 当模型加载失败、资源 404 或 WebView 未初始化时，显示具体原因。
- 让用户能够区分“窗口没出来”和“窗口出来但模型没加载成功”。

### 6. 验证与回归
- 运行项目并验证主窗口启动行为。
- 验证桌宠窗口是否在 Windows/macOS 正常显示。
- 验证模型是否能正常渲染并播放默认动作。
- 若存在失败点，按日志逐个修复并重新验证。

## 交付结果

完成后应达到：
- 启动项目后 Live2D 桌宠可见。
- 桌宠资源可正常加载。
- 若失败，界面能明确提示失败原因。
- 不影响原有主聊天窗口功能。
