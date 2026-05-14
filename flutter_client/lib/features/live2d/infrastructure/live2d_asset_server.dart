import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../domain/live2d_window_config.dart';

class Live2dAssetServer {
  Live2dAssetServer._(this._server);

  static Live2dAssetServer? _instance;

  static Future<Live2dAssetServer> ensureStarted() async {
    if (_instance != null) {
      return _instance!;
    }
    final HttpServer server = await HttpServer.bind(
      InternetAddress.loopbackIPv4,
      0,
      shared: true,
    );
    final Live2dAssetServer assetServer = Live2dAssetServer._(server);
    server.listen(assetServer._handleRequest);
    _instance = assetServer;
    return assetServer;
  }

  final HttpServer _server;

  Uri get viewerUri => Uri.parse(
        'http://${InternetAddress.loopbackIPv4.address}:${_server.port}'
        '/${Live2dWindowConfig.viewerRoutePrefix}/index.html',
      );

  Future<void> _handleRequest(HttpRequest request) async {
    final String path = request.uri.path == '/'
        ? '/${Live2dWindowConfig.viewerRoutePrefix}/index.html'
        : request.uri.path;
    final String assetKey = _resolveAssetKey(path);
    if (assetKey.isEmpty) {
      request.response.statusCode = HttpStatus.notFound;
      await request.response.close();
      return;
    }

    try {
      final ByteData data = await rootBundle.load(assetKey);
      final Uint8List bytes = data.buffer.asUint8List();
      request.response.headers.contentType = _contentTypeFor(path);
      request.response.headers.set('Access-Control-Allow-Origin', '*');
      request.response.add(bytes);
    } on FlutterError {
      request.response.statusCode = HttpStatus.notFound;
    } finally {
      await request.response.close();
    }
  }

  String _resolveAssetKey(String requestPath) {
    final String normalized = requestPath.startsWith('/')
        ? requestPath.substring(1)
        : requestPath;
    if (normalized == Live2dWindowConfig.viewerRoutePrefix ||
        normalized == '${Live2dWindowConfig.viewerRoutePrefix}/') {
      return 'assets/live2d/${Live2dWindowConfig.viewerRoutePrefix}/index.html';
    }
    if (normalized.startsWith('${Live2dWindowConfig.viewerRoutePrefix}/')) {
      final String assetPath = normalized.substring(
        '${Live2dWindowConfig.viewerRoutePrefix}/'.length,
      );
      return 'assets/live2d/${Live2dWindowConfig.viewerRoutePrefix}/$assetPath';
    }
    if (normalized.startsWith('${Live2dWindowConfig.runtimeRoutePrefix}/')) {
      final String assetPath = normalized.substring(
        '${Live2dWindowConfig.runtimeRoutePrefix}/'.length,
      );
      return 'assets/live2d/hiyori_pro_zh/${Live2dWindowConfig.runtimeRoutePrefix}/$assetPath';
    }
    return '';
  }

  ContentType _contentTypeFor(String path) {
    if (path.endsWith('.html')) {
      return ContentType.html;
    }
    if (path.endsWith('.js')) {
      return ContentType('application', 'javascript', charset: 'utf-8');
    }
    if (path.endsWith('.json')) {
      return ContentType.json;
    }
    if (path.endsWith('.png')) {
      return ContentType('image', 'png');
    }
    if (path.endsWith('.moc3')) {
      return ContentType('application', 'octet-stream');
    }
    return ContentType.binary;
  }
}
