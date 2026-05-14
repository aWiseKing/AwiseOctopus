import 'package:flutter/material.dart';
import 'package:flutter_client/features/live2d/application/live2d_pet_controller.dart';

class Live2dPetOverlayControls extends StatelessWidget {
  final Live2dPetController controller;

  const Live2dPetOverlayControls({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, child) {
        final state = controller.value;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: Colors.black26,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (state.statusMessage != null)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Text(
                    state.statusMessage!,
                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                  ),
                ),
              _iconButton(
                Icons.open_in_new,
                '打开主窗口',
                () => controller.openMainWindow(),
              ),
              _iconButton(
                Icons.shuffle,
                '随机动作',
                () => controller.playRandomMotion(),
              ),
              _iconButton(
                Icons.close,
                '关闭桌宠',
                () => controller.hidePet(),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _iconButton(IconData icon, String tooltip, VoidCallback onTap) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Icon(icon, size: 18, color: Colors.white70),
        ),
      ),
    );
  }
}
