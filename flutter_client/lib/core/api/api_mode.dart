enum ApiMode { mock, remote }

extension ApiModeLabel on ApiMode {
  String get label {
    switch (this) {
      case ApiMode.mock:
        return 'Mock';
      case ApiMode.remote:
        return 'Remote';
    }
  }
}
