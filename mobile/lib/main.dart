// Qaqpan — Android app.
//
// The banking module UI is the same web app the stage uses (served by the Qaqpan server), shown in a
// full-screen WebView. The native side adds what a website cannot do:
//   * the real fact of a phone call (AudioManager / TelephonyManager, no number, no audio), pushed to the
//     page as window.__qaqpanOnCall every second;
//   * Android back button that walks back through the app's screens;
//   * profile choice for the demo (Aigerim, Erzhan, Madina), remembered between launches.
//
// Server: --dart-define=QAQPAN_SERVER=https://... (defaults to the public Railway deployment). On the venue it can be
// changed without rebuilding: long-press the logo on the profile screen -> server address and presenter key.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

const kServer = String.fromEnvironment('QAQPAN_SERVER', defaultValue: 'https://qaqpan-production.up.railway.app');
const kTeal = Color(0xFF0F766E);
const kInk = Color(0xFF0F172A);
const kBg = Color(0xFFF8FAFC);
const _call = MethodChannel('kz.qaqpan/call');

class Profile {
  const Profile(this.id, this.name, this.role, this.initials);
  final String id, name, role, initials;
}

const profiles = [
  Profile('aigerim', 'Айгерим, 52', 'Клиентка банка · семейный щит включён', 'АС'),
  Profile('erzhan', 'Ержан, 27', 'Сын · доверенное лицо мамы', 'ЕС'),
  Profile('madina', 'Мадина, 34', 'Другая клиентка банка', 'МК'),
];

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
    systemNavigationBarColor: kBg,
    systemNavigationBarIconBrightness: Brightness.dark,
  ));
  runApp(const QaqpanApp());
}

class QaqpanApp extends StatelessWidget {
  const QaqpanApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Qaqpan',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: kTeal, useMaterial3: true, scaffoldBackgroundColor: kBg),
      home: const Root(),
    );
  }
}

/// Opens the remembered profile, or asks which demo client this phone is.
class Root extends StatefulWidget {
  const Root({super.key});

  @override
  State<Root> createState() => _RootState();
}

class _RootState extends State<Root> {
  String? profile;
  String server = kServer;
  String key = '';
  bool bcc = false;
  bool loaded = false;

  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance().then((p) => setState(() {
          profile = p.getString('profile');
          server = p.getString('server') ?? kServer;
          key = p.getString('key') ?? '';
          bcc = p.getBool('bcc') ?? false;
          loaded = true;
        }));
  }

  /// Hidden presenter settings: the stand's address and the presenter key (for a locked stand, QAQPAN_LOCK=1).
  Future<void> settings() async {
    final s = TextEditingController(text: server), k = TextEditingController(text: key);
    var style = bcc;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Сервер демо'),
        content: StatefulBuilder(
          builder: (ctx, setInner) => Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: s, keyboardType: TextInputType.url, decoration: const InputDecoration(labelText: 'Адрес сервера')),
            TextField(controller: k, decoration: const InputDecoration(labelText: 'Ключ ведущего (если стенд закрыт)')),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('В стиле BCC'),
              value: style,
              onChanged: (v) => setInner(() => style = v),
            ),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => s.text = kServer, child: const Text('По умолчанию')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Сохранить')),
        ],
      ),
    );
    if (ok != true) return;
    final p = await SharedPreferences.getInstance();
    final url = s.text.trim().replaceAll(RegExp(r'/+$'), '');
    await p.setString('server', url.isEmpty ? kServer : url);
    await p.setString('key', k.text.trim());
    await p.setBool('bcc', style);
    setState(() {
      server = url.isEmpty ? kServer : url;
      key = k.text.trim();
      bcc = style;
    });
  }

  Future<void> choose(String? id) async {
    final p = await SharedPreferences.getInstance();
    if (id == null) {
      await p.remove('profile');
    } else {
      await p.setString('profile', id);
    }
    setState(() => profile = id);
  }

  @override
  Widget build(BuildContext context) {
    if (!loaded) return const Splash();
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 350),
      child: profile == null
          ? ProfilePicker(key: const ValueKey('pick'), onPick: choose, onSettings: settings, server: server)
          : AppWebView(key: ValueKey('$profile@$server@$bcc'), profile: profile!, server: server, presenterKey: key, bcc: bcc,
              onSwitchProfile: () => choose(null), onSettings: settings),
    );
  }
}

class Logo extends StatelessWidget {
  const Logo({super.key, this.size = 72});
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: const Color(0xFF10B981), borderRadius: BorderRadius.circular(size * 0.28)),
      child: Icon(Icons.shield_outlined, color: Colors.white, size: size * 0.55),
    );
  }
}

class Splash extends StatelessWidget {
  const Splash({super.key, this.message});
  final String? message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Logo(),
          const SizedBox(height: 16),
          Text(message ?? 'Qaqpan', style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 15)),
        ]),
      ),
    );
  }
}

class ProfilePicker extends StatelessWidget {
  const ProfilePicker({super.key, required this.onPick, this.onSettings, this.server = kServer});
  final ValueChanged<String> onPick;
  final VoidCallback? onSettings;
  final String server;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.fromLTRB(20, 32, 20, 24), children: [
          Align(
            alignment: Alignment.centerLeft,
            child: GestureDetector(onLongPress: onSettings, child: const Logo(size: 64)),
          ),
          const SizedBox(height: 20),
          const Text('Qaqpan', style: TextStyle(fontSize: 34, fontWeight: FontWeight.w900, color: kInk)),
          const SizedBox(height: 6),
          const Text('Капкан для мошенников внутри приложения банка',
              style: TextStyle(fontSize: 16, color: Color(0xFF475569))),
          const SizedBox(height: 28),
          const Text('Чей это телефон в демо?',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF64748B))),
          const SizedBox(height: 10),
          for (final p in profiles)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                child: InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: () => onPick(p.id),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(children: [
                      CircleAvatar(
                        radius: 24,
                        backgroundColor: const Color(0xFFCCFBF1),
                        child: Text(p.initials, style: const TextStyle(color: kTeal, fontWeight: FontWeight.w800)),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(p.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: kInk)),
                          const SizedBox(height: 2),
                          Text(p.role, style: const TextStyle(fontSize: 13, color: Color(0xFF64748B))),
                        ]),
                      ),
                      const Icon(Icons.chevron_right, color: Color(0xFFCBD5E1)),
                    ]),
                  ),
                ),
              ),
            ),
          const SizedBox(height: 16),
          const Text(
            'Приложение попросит доступ к состоянию телефона — только чтобы знать, идёт ли сейчас звонок. '
            'Номер и разговор Qaqpan не видит.',
            style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8), height: 1.4),
          ),
          if (server != kServer) ...[
            const SizedBox(height: 8),
            Text('Сервер: $server', style: const TextStyle(fontSize: 12, color: kTeal)),
          ],
        ]),
      ),
    );
  }
}

class AppWebView extends StatefulWidget {
  const AppWebView(
      {super.key,
      required this.profile,
      required this.onSwitchProfile,
      this.server = kServer,
      this.presenterKey = '',
      this.bcc = false,
      this.onSettings});
  final String profile;
  final String server;
  final String presenterKey;
  final bool bcc;
  final VoidCallback onSwitchProfile;
  final VoidCallback? onSettings;

  @override
  State<AppWebView> createState() => _AppWebViewState();
}

class _AppWebViewState extends State<AppWebView> {
  late final WebViewController web;
  Timer? callTimer;
  bool? lastOnCall;
  bool ready = false;
  String? error;

  Uri get home => Uri.parse('${widget.server}/phone/${widget.profile}').replace(queryParameters: {
        'theme': widget.bcc ? 'bcc' : 'default',
        if (widget.presenterKey.isNotEmpty) 'key': widget.presenterKey,
      });

  @override
  void initState() {
    super.initState();
    web = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(kBg)
      ..setNavigationDelegate(NavigationDelegate(
        // «Позвонить маме» (tel:) and links to other sites open in the phone's own apps, not inside the WebView
        onNavigationRequest: (req) {
          final uri = Uri.tryParse(req.url);
          if (uri == null || uri.host == home.host && uri.scheme.startsWith('http')) return NavigationDecision.navigate;
          launchUrl(uri, mode: LaunchMode.externalApplication).catchError((_) => false);
          return NavigationDecision.prevent;
        },
        onPageFinished: (_) {
          lastOnCall = null; // re-push the call state into the fresh page
          if (mounted) setState(() => ready = true);
        },
        onWebResourceError: (e) {
          if (e.isForMainFrame ?? true) setState(() => error = 'Нет связи с сервером Qaqpan');
        },
      ))
      ..loadRequest(home);
    _call.invokeMethod('requestPhonePermission').catchError((_) => null);
    callTimer = Timer.periodic(const Duration(seconds: 1), (_) => pushCallState());
  }

  Future<void> pushCallState() async {
    if (!ready) return;
    try {
      final onCall = await _call.invokeMethod<bool>('isOnCall') ?? false;
      if (onCall == lastOnCall) return;
      lastOnCall = onCall;
      await web.runJavaScript('window.__qaqpanOnCall = $onCall;');
    } catch (_) {/* bridge unavailable: the director can still simulate calls */}
  }

  Future<void> retry() async {
    setState(() {
      error = null;
      ready = false;
    });
    await web.loadRequest(home);
  }

  /// Android back: go one screen back inside the app; on the home screen offer to switch profile or exit.
  Future<void> onBack() async {
    final went = await web.runJavaScriptReturningResult(
        "(() => { const b = document.querySelector('button[aria-label=\"back\"]'); if (b) { b.click(); return 'yes'; } return 'no'; })()");
    if ('$went'.contains('yes') || !mounted) return;
    final action = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.swap_horiz), title: const Text('Сменить профиль демо'),
              onTap: () => Navigator.pop(ctx, 'switch')),
          ListTile(leading: const Icon(Icons.refresh), title: const Text('Обновить'), onTap: () => Navigator.pop(ctx, 'reload')),
          ListTile(leading: const Icon(Icons.dns_outlined), title: const Text('Сервер демо'),
              onTap: () => Navigator.pop(ctx, 'server')),
          ListTile(leading: const Icon(Icons.close), title: const Text('Выйти'), onTap: () => Navigator.pop(ctx, 'exit')),
        ]),
      ),
    );
    if (action == 'switch') widget.onSwitchProfile();
    if (action == 'reload') retry();
    if (action == 'server') widget.onSettings?.call();
    if (action == 'exit') SystemNavigator.pop();
  }

  @override
  void dispose() {
    callTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) onBack();
      },
      child: Scaffold(
        body: SafeArea(
          bottom: false,
          child: Stack(children: [
            WebViewWidget(controller: web),
            if (!ready && error == null) const Splash(),
            if (error != null)
              Container(
                color: kBg,
                alignment: Alignment.center,
                padding: const EdgeInsets.all(32),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Logo(size: 56),
                  const SizedBox(height: 16),
                  Text(error!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, color: kInk)),
                  const SizedBox(height: 6),
                  const Text('Проверьте интернет и попробуйте ещё раз', style: TextStyle(color: Color(0xFF64748B))),
                  const SizedBox(height: 20),
                  FilledButton(onPressed: retry, child: const Text('Повторить')),
                ]),
              ),
          ]),
        ),
      ),
    );
  }
}
