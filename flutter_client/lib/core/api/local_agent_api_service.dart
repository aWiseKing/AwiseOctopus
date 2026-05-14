import 'dart:async';
import 'dart:io';

class LocalAgentApiService {
  LocalAgentApiService({
    this.host = '127.0.0.1',
    this.port = 9009,
    String? pythonExecutable,
    ProcessStarter? processStarter,
    HealthChecker? healthChecker,
    Directory? workingDirectory,
  })  : _pythonExecutable = pythonExecutable,
        _processStarter = processStarter ?? Process.start,
        _healthChecker = healthChecker ?? _defaultHealthCheck,
        _workingDirectory = workingDirectory;

  final String host;
  final int port;
  final String? _pythonExecutable;
  final ProcessStarter _processStarter;
  final HealthChecker _healthChecker;
  final Directory? _workingDirectory;

  Process? _process;
  Future<void>? _startFuture;

  Uri get baseUri => Uri.parse('http://$host:$port');

  Future<void> ensureStarted() {
    _startFuture ??= _start();
    return _startFuture!;
  }

  Future<void> _start() async {
    if (await _healthChecker(baseUri)) {
      return;
    }

    final Directory root = _workingDirectory ?? _resolveRepoRoot();
    final String executable = _pythonExecutable ??
        Platform.environment['AWISE_AGENT_PYTHON'] ??
        'python';
    final Process process = await _processStarter(
      executable,
      <String>[
        '-m',
        'uvicorn',
        'api_server:app',
        '--host',
        host,
        '--port',
        '$port',
      ],
      workingDirectory: root.path,
      mode: ProcessStartMode.detachedWithStdio,
    );
    _process = process;
    unawaited(process.stdout.drain<void>());
    unawaited(process.stderr.drain<void>());
  }

  Future<void> stop() async {
    final Process? process = _process;
    _process = null;
    _startFuture = null;
    process?.kill();
  }

  static Future<bool> _defaultHealthCheck(Uri baseUri) async {
    final HttpClient client = HttpClient()
      ..connectionTimeout = const Duration(milliseconds: 500);
    try {
      final HttpClientRequest request =
          await client.getUrl(baseUri.resolve('/api/health'));
      final HttpClientResponse response =
          await request.close().timeout(const Duration(seconds: 1));
      await response.drain<void>();
      return response.statusCode == HttpStatus.ok;
    } catch (_) {
      return false;
    } finally {
      client.close(force: true);
    }
  }

  Directory _resolveRepoRoot() {
    final String? configured = Platform.environment['AWISE_AGENT_ROOT'];
    if (configured != null && configured.trim().isNotEmpty) {
      return Directory(configured);
    }

    final List<Directory> candidates = <Directory>[
      Directory.current,
      File(Platform.resolvedExecutable).parent,
    ];
    for (final Directory candidate in candidates) {
      final Directory? root = _findRepoRoot(candidate);
      if (root != null) {
        return root;
      }
    }
    return Directory.current;
  }

  Directory? _findRepoRoot(Directory start) {
    Directory current = start.absolute;
    while (true) {
      if (File('${current.path}${Platform.pathSeparator}api_server.py')
          .existsSync()) {
        return current;
      }
      final Directory parent = current.parent;
      if (parent.path == current.path) {
        return null;
      }
      current = parent;
    }
  }
}

typedef ProcessStarter = Future<Process> Function(
  String executable,
  List<String> arguments, {
  String? workingDirectory,
  ProcessStartMode mode,
});

typedef HealthChecker = Future<bool> Function(Uri baseUri);
