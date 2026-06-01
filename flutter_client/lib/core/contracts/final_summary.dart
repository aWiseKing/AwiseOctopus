class FinalSummary {
  const FinalSummary({required this.content});

  final String content;

  factory FinalSummary.fromJson(Map<String, dynamic> json) {
    return FinalSummary(content: json['content'] as String? ?? '');
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{'content': content};
  }
}
