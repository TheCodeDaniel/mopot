import 'package:flutter/material.dart';

void main() {
  runApp(const MopotDemoApp());
}

class MopotDemoApp extends StatelessWidget {
  const MopotDemoApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mopot Demo',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      initialRoute: '/home',
      routes: {
        '/home': (context) => const HomeScreen(),
        '/settings': (context) => const SettingsScreen(),
        // BUG 3: '/details' route is intentionally missing.
        // Tapping the info button throws RouteException at runtime.
      },
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // BUG 1: _items is nullable and never initialised before first build.
  // Accessing _items.length on the first render throws:
  //   Null check operator used on a null value
  List<String>? _items;

  void _addItem() {
    setState(() {
      _items ??= [];
      _items!.add('Task ${_items!.length + 1}');
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mopot Demo — Home'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.pushNamed(context, '/settings'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // BUG 2: Unbounded Text inside a Row without Expanded.
            // Causes RenderFlex overflow on screens narrower than the text.
            Row(
              children: [
                Text(
                  'Total tasks in your list today: ${_items!.length}',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const Icon(Icons.list_alt, size: 24),
              ],
            ),
            const SizedBox(height: 16),
            Expanded(
              child: _items == null || _items!.isEmpty
                  ? const Center(child: Text('No tasks yet. Add one below!'))
                  : ListView.builder(
                      itemCount: _items!.length,
                      itemBuilder: (context, index) => ListTile(
                        leading: const Icon(Icons.check_circle_outline),
                        title: Text(_items![index]),
                        trailing: IconButton(
                          icon: const Icon(Icons.info_outline),
                          // BUG 3: '/details' is not registered in routes map above.
                          onPressed: () => Navigator.pushNamed(context, '/details'),
                        ),
                      ),
                    ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addItem,
        label: const Text('Add Task'),
        icon: const Icon(Icons.add),
      ),
    );
  }
}

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: const Center(
        child: Text('Settings — nothing configured yet.'),
      ),
    );
  }
}
