import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutter_client/features/live2d/application/live2d_pet_providers.dart';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  bool _autoStartEnabled = false;

  @override
  void initState() {
    super.initState();
    _loadAutoStart();
  }

  Future<void> _loadAutoStart() async {
    final controller = ref.read(live2dPetControllerProvider);
    final enabled = await controller.isAutoStartEnabled();
    if (mounted) {
      setState(() => _autoStartEnabled = enabled);
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = ref.read(live2dPetControllerProvider);
    final petState = controller.value;

    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _sectionHeader('桌宠设置'),
          Card(
            child: Column(
              children: [
                SwitchListTile(
                  title: const Text('启用桌宠'),
                  subtitle: const Text('在桌面显示 Live2D 角色'),
                  value: petState.enabled,
                  onChanged: (value) => controller.setEnabled(value),
                ),
                SwitchListTile(
                  title: const Text('开机自启动'),
                  subtitle: const Text('系统登录后自动显示桌宠'),
                  value: _autoStartEnabled,
                  onChanged: (value) async {
                    await controller.setAutoStartEnabled(value);
                    setState(() => _autoStartEnabled = value);
                  },
                ),
                ListTile(
                  title: Text(
                    petState.petWindowVisible ? '隐藏桌宠' : '显示桌宠',
                  ),
                  leading: Icon(
                    petState.petWindowVisible
                        ? Icons.visibility_off
                        : Icons.pets,
                  ),
                  onTap: () => controller.togglePet(),
                ),
                ListTile(
                  title: const Text('重置位置'),
                  subtitle: const Text('将桌宠移回右下角'),
                  leading: const Icon(Icons.restore),
                  onTap: () => controller.resetPosition(),
                ),
                ListTile(
                  title: const Text('测试随机动作'),
                  subtitle: const Text('播放一个随机 Live2D 动作'),
                  leading: const Icon(Icons.play_circle_outline),
                  onTap: () => controller.playRandomMotion(),
                ),
                if (petState.statusMessage != null)
                  ListTile(
                    title: Text(
                      '状态: ${petState.statusMessage}',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    leading: const Icon(Icons.info_outline, size: 18),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          _sectionHeader('API 设置'),
          Card(
            child: ListTile(
              title: const Text('Agent API 模式'),
              subtitle: const Text('当前: Mock API'),
              leading: const Icon(Icons.api),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {},
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: Colors.grey,
            ),
      ),
    );
  }
}
