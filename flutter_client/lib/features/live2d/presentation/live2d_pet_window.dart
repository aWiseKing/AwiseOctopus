import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:window_manager/window_manager.dart';

import 'package:flutter_client/features/live2d/application/live2d_pet_controller.dart';
import 'package:flutter_client/features/live2d/presentation/live2d_pet_overlay_controls.dart';

class Live2dPetWindow extends StatefulWidget {
  final Live2dPetController controller;

  const Live2dPetWindow({super.key, required this.controller});

  @override
  State<Live2dPetWindow> createState() => _Live2dPetWindowState();
}

class _Live2dPetWindowState extends State<Live2dPetWindow> {
  WebViewController? _webviewController;

  @override
  void initState() {
    super.initState();
    widget.controller.bridge.attach(_evaluateJavascript);
    _initWebView();
  }

  Future<void> _initWebView() async {
    _webviewController = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.transparent)
      ..addJavaScriptChannel(
        'Live2DChannel',
        onMessageReceived: _onMessageReceived,
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            widget.controller.setStatusMessage('page loaded');
          },
        ),
      )
      ..loadFlutterAsset('assets/live2d/viewer/index.html');

    setState(() {});
  }

  @override
  void dispose() {
    widget.controller.bridge.detach();
    super.dispose();
  }

  void _evaluateJavascript(String script) {
    _webviewController?.runJavaScript(script);
  }

  void _onMessageReceived(JavaScriptMessage message) {
    widget.controller.bridge.handleMessage(message.message);
  }

  @override
  Widget build(BuildContext context) {
    if (_webviewController == null) {
      return const Scaffold(
        backgroundColor: Colors.transparent,
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(
        children: [
          Positioned.fill(
            child: WebViewWidget(controller: _webviewController!),
          ),
          const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: DragToMoveArea(
              child: SizedBox(height: 36),
            ),
          ),
          Positioned(
            bottom: 8,
            left: 8,
            right: 8,
            child: Live2dPetOverlayControls(
              controller: widget.controller,
            ),
          ),
        ],
      ),
    );
  }
}
