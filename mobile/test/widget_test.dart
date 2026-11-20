import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qaqpan/main.dart';

void main() {
  testWidgets('profile picker lists the three demo clients and reports the choice', (tester) async {
    String? picked;
    await tester.pumpWidget(MaterialApp(home: ProfilePicker(onPick: (id) => picked = id)));
    expect(find.text('Qaqpan'), findsOneWidget);
    for (final p in profiles) {
      expect(find.text(p.name), findsOneWidget);
    }
    await tester.tap(find.text('Ержан, 27'));
    expect(picked, 'erzhan');
  });
}
