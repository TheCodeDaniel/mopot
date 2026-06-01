// Widget tests for the Mopot demo app.
// These tests intentionally expose the 3 bugs so the pipeline has failing tests to detect.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:sample_flutter_app/main.dart';

void main() {
  testWidgets('HomeScreen renders without crashing', (WidgetTester tester) async {
    // BUG 1 will cause this test to fail — null check on _items.length at build time.
    await tester.pumpWidget(const MopotDemoApp());
    await tester.pump();
    expect(find.text('Mopot Demo — Home'), findsOneWidget);
  });

  testWidgets('Task list row does not overflow', (WidgetTester tester) async {
    await tester.pumpWidget(const MopotDemoApp());
    await tester.pump();

    // Tap Add Task to put an item in the list
    await tester.tap(find.text('Add Task'));
    await tester.pump();

    // BUG 2: Row overflow error is thrown here — no Expanded wrapper on the Text
    expect(tester.takeException(), isNull);
  });

  testWidgets('Details route exists and navigates', (WidgetTester tester) async {
    await tester.pumpWidget(const MopotDemoApp());
    await tester.pump();

    // Add a task so the info button appears
    await tester.tap(find.text('Add Task'));
    await tester.pump();

    // BUG 3: Tapping info navigates to '/details' which is not registered
    await tester.tap(find.byIcon(Icons.info_outline));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });
}
