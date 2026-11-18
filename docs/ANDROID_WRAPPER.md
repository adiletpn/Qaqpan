# Настоящий сигнал звонка на Android (к финалу 11.12)

В браузере сайт не может узнать, идёт ли звонок, поэтому в демо сигнал подаётся с пульта. В приложении банка это
системный API. Чтобы показать на финале живой сигнал, хватает тонкой обёртки: WebView + JS-мост.
Веб-часть уже готова: `web/src/native.ts` раз в секунду вызывает `window.QalqanNative.isOnCall()` и отправляет
факт звонка в `POST /api/phone/{id}/native-call`. Номер и содержание разговора не передаются.

## Минимальная обёртка (Kotlin)

`MainActivity.kt`:

```kotlin
class MainActivity : AppCompatActivity() {
    private lateinit var web: WebView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.addJavascriptInterface(CallBridge(getSystemService(AUDIO_SERVICE) as AudioManager), "QalqanNative")
        web.loadUrl(BuildConfig.QALQAN_URL + "/phone/aigerim")
        setContentView(web)
    }
}

class CallBridge(private val audio: AudioManager) {
    // Только факт звонка: обычный звонок или звонок в мессенджере. Без разрешений.
    @JavascriptInterface
    fun isOnCall(): Boolean =
        audio.mode == AudioManager.MODE_IN_CALL || audio.mode == AudioManager.MODE_IN_COMMUNICATION
}
```

`build.gradle` (модуль): `buildConfigField "String", "QALQAN_URL", "\"https://<ваш-деплой>\""`.
`AndroidManifest.xml`: `<uses-permission android:name="android.permission.INTERNET" />`.

Если `getMode()` на конкретном телефоне не отражает звонки других приложений, используйте
`TelephonyManager.registerTelephonyCallback` (`CallStateListener`, нужно разрешение `READ_PHONE_STATE`).
Проверьте на телефоне, с которым пойдёте на сцену, заранее.

## Как показать на сцене

1. Телефон с обёрткой подключён по USB, экран выведен на проектор через `scrcpy`.
2. Напарник звонит на этот телефон с другого номера → в приложении появляется зелёная плашка звонка.
3. Перевод во время звонка получает признак «идёт телефонный звонок».

Если не успеваете — оставьте сигнал с пульта и честно скажите: «в прототипе симулируем, в приложении банка это
системный API `AudioManager.getMode()` / `CXCallObserver`».

## iOS

Аналог — `CXCallObserver` (CallKit): `callObserver.calls.contains { !$0.hasEnded }`. Мост такой же: `WKScriptMessageHandler`
или инъекция `window.QalqanNative` через `WKUserScript`.
