import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_client/features/live2d/application/live2d_pet_controller.dart';

final live2dPetControllerProvider =
    ChangeNotifierProvider<Live2dPetController>((ref) {
  return Live2dPetController();
});
