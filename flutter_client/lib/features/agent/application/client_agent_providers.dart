import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/local_agent_api_service.dart';
import '../../../core/api/mock_agent_api.dart';
import 'client_agent_controller.dart';
import 'client_agent_state.dart';

final mockAgentApiProvider = Provider<MockAgentApi>((ref) {
  return MockAgentApi();
});

final localAgentApiServiceProvider = Provider<LocalAgentApiService>((ref) {
  return LocalAgentApiService();
});

final clientAgentControllerProvider =
    StateNotifierProvider<ClientAgentController, ClientAgentState>((ref) {
  final controller = ClientAgentController(
    mockApi: ref.watch(mockAgentApiProvider),
    localService: ref.watch(localAgentApiServiceProvider),
  );
  controller.initialize();
  return controller;
});
