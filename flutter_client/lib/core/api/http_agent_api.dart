import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../contracts/agent_event.dart';
import '../contracts/agent_message.dart';
import '../contracts/agent_session.dart';
import '../contracts/approval_request.dart';
import 'agent_api.dart';

class HttpAgentApi implements AgentApi {
  HttpAgentApi({
    required this.baseUrl,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  Uri _uri(String path) => Uri.parse(baseUrl).resolve(path);

  @override
  Future<List<AgentSession>> listSessions() async {
    final response = await _client.get(_uri('/api/sessions'));
    _ensureSuccess(response);
    final list = jsonDecode(response.body) as List<dynamic>;
    return list
        .map((e) => AgentSession.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<AgentSession> createSession() async {
    final response = await _client.post(_uri('/api/sessions'));
    _ensureSuccess(response);
    return AgentSession.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  @override
  Future<List<AgentMessage>> loadSessionHistory(String sessionId) async {
    final response =
        await _client.get(_uri('/api/sessions/$sessionId/messages'));
    _ensureSuccess(response);
    final list = jsonDecode(response.body) as List<dynamic>;
    return list
        .map((e) => AgentMessage.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Stream<AgentEvent> sendPrompt({
    required String sessionId,
    required String prompt,
  }) {
    return _postNdjson('/api/agent/send-prompt', <String, dynamic>{
      'sessionId': sessionId,
      'prompt': prompt,
    });
  }

  @override
  Stream<AgentEvent> replyToAskUser({
    required String sessionId,
    required String reply,
  }) {
    return _postNdjson('/api/agent/reply-to-ask-user', <String, dynamic>{
      'sessionId': sessionId,
      'reply': reply,
    });
  }

  @override
  Stream<AgentEvent> submitApprovalDecision({
    required String sessionId,
    required ApprovalDecision decision,
  }) {
    return _postNdjson('/api/agent/approval-decision', <String, dynamic>{
      'sessionId': sessionId,
      'decision': decision.label,
    });
  }

  Stream<AgentEvent> _postNdjson(
    String path,
    Map<String, dynamic> body,
  ) async* {
    final request = http.Request('POST', _uri(path))
      ..headers[HttpHeaders.contentTypeHeader] =
          'application/json; charset=utf-8'
      ..headers[HttpHeaders.acceptHeader] = 'application/x-ndjson'
      ..body = jsonEncode(body);

    final streamedResponse = await _client.send(request);
    _ensureSuccessStreamed(streamedResponse);

    await for (final line in streamedResponse.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())) {
      final trimmed = line.trim();
      if (trimmed.isEmpty) continue;
      final json = jsonDecode(trimmed) as Map<String, dynamic>;
      yield AgentEvent.fromJson(json);
    }
  }

  void _ensureSuccess(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HttpException(
        'HTTP ${response.statusCode}: ${response.body}',
        uri: response.request?.url,
      );
    }
  }

  void _ensureSuccessStreamed(http.StreamedResponse response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw HttpException(
        'HTTP ${response.statusCode}',
        uri: response.request?.url,
      );
    }
  }
}
