package com.ghazalatransport.pos;

import android.app.Activity;
import android.app.AlertDialog;
import android.print.PrintManager;
import android.content.Context;
import android.content.Intent;
import android.content.ComponentName;
import android.content.ServiceConnection;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.os.IBinder;
import android.print.PrintDocumentAdapter;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;
import org.json.JSONObject;
import java.lang.reflect.Method;
import java.io.InputStream;

public class MainActivity extends Activity {
    private static final String PREFS = "ghazala_pos_prefs";
    private static final String PREF_SERVER_URL = "server_url";
    private WebView webView;
    private ProgressBar progress;
    private SharedPreferences prefs;
    private Object sunmiPrinterService;
    private boolean sunmiBound=false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        buildUi();
        bindSunmiPrinter();

        String serverUrl = normalizeUrl(prefs.getString(PREF_SERVER_URL, ""));
        if (serverUrl.isEmpty()) {
            showServerDialog(true);
        } else {
            loadServer(serverUrl);
        }
    }

    private void buildUi() {
        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);

        FrameLayout.LayoutParams webParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        );
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                8
        );

        root.addView(webView, webParams);
        root.addView(progress, progressParams);
        setContentView(root);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setTextZoom(100);
        webView.setInitialScale(0);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        settings.setUserAgentString(settings.getUserAgentString() + " GhazalaPOS/0.1");

        webView.addJavascriptInterface(new PosBridge(this), "GhazalaPOSPrinter");
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progress.setProgress(newProgress);
                progress.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progress.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    Toast.makeText(MainActivity.this,
                            "Server connect nahi ho raha. Network/IP check karein.",
                            Toast.LENGTH_LONG).show();
                }
            }
        });

        webView.setOnLongClickListener(v -> {
            showServerDialog(false);
            return true;
        });
        webView.setLongClickable(true);
        webView.setHapticFeedbackEnabled(false);
    }


    private void bindSunmiPrinter() {
        try {
            Intent intent = new Intent("woyou.aidlservice.jiuiv5.IWoyouService");
            intent.setPackage("woyou.aidlservice.jiuiv5");
            sunmiBound = bindService(intent, sunmiConnection, Context.BIND_AUTO_CREATE);
        } catch (Exception ex) {
            sunmiBound = false;
        }
    }

    private final ServiceConnection sunmiConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            try {
                Context pkg = createPackageContext(
                        "woyou.aidlservice.jiuiv5",
                        Context.CONTEXT_INCLUDE_CODE | Context.CONTEXT_IGNORE_SECURITY
                );
                Class<?> stub = pkg.getClassLoader().loadClass(
                        "woyou.aidlservice.jiuiv5.IWoyouService$Stub"
                );
                Method asInterface = stub.getMethod("asInterface", IBinder.class);
                sunmiPrinterService = asInterface.invoke(null, service);
                Toast.makeText(MainActivity.this,
                        "SUNMI thermal printer connected.",
                        Toast.LENGTH_SHORT).show();
            } catch (Exception ex) {
                sunmiPrinterService = null;
                Toast.makeText(MainActivity.this,
                        "SUNMI printer service mila, lekin interface load nahi hui.",
                        Toast.LENGTH_LONG).show();
            }
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            sunmiPrinterService = null;
        }
    };

    private Object invokeSunmi(String name, Object... args) throws Exception {
        if (sunmiPrinterService == null) {
            throw new IllegalStateException("SUNMI printer service connected nahi hai.");
        }
        Method match = null;
        Method[] methods = sunmiPrinterService.getClass().getMethods();
        for (Method method : methods) {
            if (method.getName().equals(name) && method.getParameterTypes().length == args.length) {
                match = method;
                break;
            }
        }
        if (match == null) throw new NoSuchMethodException(name);
        match.setAccessible(true);
        return match.invoke(sunmiPrinterService, args);
    }

    private String printerStatus() {
        if (!sunmiBound) return "NOT_BOUND";
        if (sunmiPrinterService == null) return "NOT_READY";
        return "READY";
    }

    private Bitmap loadOfficialLogo() {
        try {
            InputStream in = getAssets().open("ghazala-logo-original.png");
            Bitmap original = BitmapFactory.decodeStream(in);
            in.close();
            if (original == null) return null;

            // Thermal printers turn the dark brand background into a solid block.
            // Build a light edge/outline version instead so the Ghazala artwork stays readable.
            int targetWidth = 210;
            int targetHeight = Math.max(1, Math.round(original.getHeight() * (targetWidth / (float) original.getWidth())));
            Bitmap scaled = Bitmap.createScaledBitmap(original, targetWidth, targetHeight, true);
            Bitmap thermal = Bitmap.createBitmap(targetWidth, targetHeight, Bitmap.Config.ARGB_8888);

            int[][] gray = new int[targetHeight][targetWidth];
            for (int y = 0; y < targetHeight; y++) {
                for (int x = 0; x < targetWidth; x++) {
                    int p = scaled.getPixel(x, y);
                    int a = Color.alpha(p);
                    if (a < 24) {
                        gray[y][x] = 255;
                    } else {
                        gray[y][x] = Math.round(
                                0.299f * Color.red(p) +
                                0.587f * Color.green(p) +
                                0.114f * Color.blue(p));
                    }
                    thermal.setPixel(x, y, Color.WHITE);
                }
            }

            for (int y = 1; y < targetHeight - 1; y++) {
                for (int x = 1; x < targetWidth - 1; x++) {
                    int gx =
                            -gray[y-1][x-1] + gray[y-1][x+1] +
                            -2*gray[y][x-1] + 2*gray[y][x+1] +
                            -gray[y+1][x-1] + gray[y+1][x+1];
                    int gy =
                            -gray[y-1][x-1] - 2*gray[y-1][x] - gray[y-1][x+1] +
                             gray[y+1][x-1] + 2*gray[y+1][x] + gray[y+1][x+1];
                    int magnitude = Math.abs(gx) + Math.abs(gy);
                    if (magnitude > 135) {
                        thermal.setPixel(x, y, Color.BLACK);
                    }
                }
            }

            return thermal;
        } catch (Exception ignored) {
            return null;
        }
    }

    private void printColumns(String left, String right) throws Exception {
        invokeSunmi("printColumnsString",
                new String[]{left, right},
                new int[]{1, 1},
                new int[]{0, 2},
                null);
    }

    private String printSunmiReceipt(String json) {
        try {
            if (sunmiPrinterService == null) {
                return "PRINTER_NOT_READY";
            }
            JSONObject data = new JSONObject(json);
            String awb = data.optString("awb", "");
            String sender = data.optString("sender", "");
            String senderMobile = data.optString("senderMobile", "");
            String recipient = data.optString("recipient", "");
            String recipientMobile = data.optString("recipientMobile", "");
            String route = data.optString("route", "");
            String payment = data.optString("payment", "");
            String date = data.optString("date", "");
            String time = data.optString("time", "");
            String branch = data.optString("branch", "");

            invokeSunmi("printerInit", new Object[]{null});
            invokeSunmi("setAlignment", 1, null);

            invokeSunmi("setFontSize", 34.0f, null);
            invokeSunmi("printText", "GHAZALA TRANSPORT\n", null);
            invokeSunmi("setFontSize", 26.0f, null);
            invokeSunmi("printText", "غزالا ترانسبورت\n", null);
            invokeSunmi("setFontSize", 18.0f, null);
            invokeSunmi("printText", "• • • • • • • • • • • • • •\n", null);

            invokeSunmi("setFontSize", 28.0f, null);
            invokeSunmi("printText", "SHIPMENT RECEIPT\n", null);
            invokeSunmi("setFontSize", 23.0f, null);
            invokeSunmi("printText", "إيصال الشحنة\n", null);
            invokeSunmi("setFontSize", 18.0f, null);
            invokeSunmi("printText", "--------------------------------\n", null);

            // Tracking codes stay at the top so customers and staff can scan immediately.
            invokeSunmi("setAlignment", 1, null);
            invokeSunmi("printQRCode", awb, 7, 1, null);
            invokeSunmi("lineWrap", 1, null);

            // Show the tracking/AWB once, directly under the QR code.
            invokeSunmi("setFontSize", 20.0f, null);
            invokeSunmi("printText", awb + "\n", null);
            invokeSunmi("lineWrap", 1, null);

            // Barcode only: force center alignment and move the next content to a fresh line.
            invokeSunmi("setAlignment", 1, null);
            invokeSunmi("printBarCode", awb, 8, 105, 2, 0, null);
            invokeSunmi("lineWrap", 2, null);
            invokeSunmi("setFontSize", 18.0f, null);
            invokeSunmi("printText", "--------------------------------\n", null);

            invokeSunmi("setAlignment", 0, null);
            invokeSunmi("setFontSize", 18.0f, null);
            printColumns("AWB / رقم الشحنة", awb);
            printColumns("Date / التاريخ", date);
            printColumns("Time / الوقت", time);
            printColumns("Branch / الفرع", branch);
            invokeSunmi("printText", "--------------------------------\n", null);

            printColumns("Sender / المرسل", sender);
            printColumns("Sender Mobile / جوال المرسل", senderMobile);
            printColumns("Recipient / المستلم", recipient);
            printColumns("Receiver Mobile / جوال المستلم", recipientMobile);
            invokeSunmi("printText", "--------------------------------\n", null);

            printColumns("Route / المسار", route);
            printColumns("Payment / الدفع", payment);
            invokeSunmi("setFontSize", 18.0f, null);
            invokeSunmi("printText", "--------------------------------\n", null);

            invokeSunmi("setFontSize", 20.0f, null);
            invokeSunmi("printText", "Thank you for shipping with Ghazala\n", null);
            invokeSunmi("setFontSize", 18.0f, null);
            invokeSunmi("printText", "شكراً لاستخدامكم غزالا ترانسبورت\n", null);
            invokeSunmi("setFontSize", 15.0f, null);
            invokeSunmi("printText", "Scan QR to track shipment / امسح QR لتتبع الشحنة\n", null);
            invokeSunmi("lineWrap", 2, null);

            return "OK";
        } catch (Exception ex) {
            return "ERROR:" + ex.getClass().getSimpleName() + ":" + String.valueOf(ex.getMessage());
        }
    }

    private String testSunmiPrinter() {
        try {
            if (sunmiPrinterService == null) return "PRINTER_NOT_READY";
            invokeSunmi("printerInit", new Object[]{null});
            invokeSunmi("setAlignment", 1, null);
            invokeSunmi("setFontSize", 26.0f, null);
            invokeSunmi("printText", "GHAZALA TRANSPORT\n", null);
            invokeSunmi("setFontSize", 20.0f, null);
            invokeSunmi("printText", "SUNMI V2 PRINTER TEST\n", null);
            invokeSunmi("printText", "Printer connection OK\n", null);
            invokeSunmi("lineWrap", 4, null);
            return "OK";
        } catch (Exception ex) {
            return "ERROR:" + ex.getClass().getSimpleName() + ":" + String.valueOf(ex.getMessage());
        }
    }

    private void showServerDialog(boolean required) {
        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(prefs.getString(PREF_SERVER_URL, "http://192.168.1.25:8000/"));
        input.setSelection(input.getText().length());

        AlertDialog.Builder builder = new AlertDialog.Builder(this)
                .setTitle("Ghazala POS Server")
                .setMessage("PC ka local server URL enter karein. Example: http://192.168.1.25:8000/")
                .setView(input)
                .setPositiveButton("Connect", (dialog, which) -> {
                    String url = normalizeUrl(input.getText().toString());
                    if (url.isEmpty()) {
                        Toast.makeText(this, "Valid server URL enter karein.", Toast.LENGTH_LONG).show();
                        showServerDialog(true);
                        return;
                    }
                    prefs.edit().putString(PREF_SERVER_URL, url).apply();
                    loadServer(url);
                });

        if (!required) {
            builder.setNegativeButton("Cancel", null);
        } else {
            builder.setCancelable(false);
        }
        builder.show();
    }

    private String normalizeUrl(String raw) {
        String value = raw == null ? "" : raw.trim();
        if (value.isEmpty()) return "";
        if (!value.startsWith("http://") && !value.startsWith("https://")) {
            value = "http://" + value;
        }
        if (!value.endsWith("/")) value += "/";
        return value;
    }

    private void loadServer(String url) {
        try { webView.clearCache(true); } catch (Exception ignored) {}
        if (!networkAvailable()) {
            Toast.makeText(this, "Wi-Fi/network available nahi hai.", Toast.LENGTH_LONG).show();
        }
        webView.loadUrl(url);
    }

    private boolean networkAvailable() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return false;
        NetworkCapabilities caps = cm.getNetworkCapabilities(cm.getActiveNetwork());
        return caps != null && (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                || caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
                || caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR));
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView != null && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        if (sunmiBound) {
            try { unbindService(sunmiConnection); } catch (Exception ignored) {}
        }
        super.onDestroy();
    }

    private final class PosBridge {
        private final Activity activity;

        PosBridge(Activity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void printHtml(String html, int paperWidthMm) {
            activity.runOnUiThread(() -> printHtmlContent(html));
        }

        @JavascriptInterface
        public String getBridgeVersion() {
            return "0.18.0-centered-clean-barcode";
        }

        @JavascriptInterface
        public String getPrinterStatus() {
            return printerStatus();
        }

        @JavascriptInterface
        public String testPrinter() {
            return testSunmiPrinter();
        }

        @JavascriptInterface
        public String printReceipt(String json) {
            return printSunmiReceipt(json);
        }

        @JavascriptInterface
        public void printWaybill(String awb, int paperWidthMm) {
            activity.runOnUiThread(() -> {
                Toast.makeText(activity,
                        "Waybill print data web portal se tayar hota hai.",
                        Toast.LENGTH_SHORT).show();
            });
        }

        private void printHtmlContent(String html) {
            try {
                final PrintManager printManager = (PrintManager) getSystemService(Context.PRINT_SERVICE);
                if (printManager == null) {
                    Toast.makeText(activity,
                            "Android print service available nahi hai. Vendor printer SDK chahiye.",
                            Toast.LENGTH_LONG).show();
                    return;
                }

                final WebView printView = new WebView(activity);
                WebSettings printSettings = printView.getSettings();
                printSettings.setJavaScriptEnabled(true);
                printSettings.setDomStorageEnabled(true);
                printSettings.setDefaultTextEncodingName("utf-8");

                printView.setWebViewClient(new WebViewClient() {
                    @Override
                    public void onPageFinished(WebView view, String url) {
                        try {
                            PrintDocumentAdapter adapter =
                                    printView.createPrintDocumentAdapter("Ghazala POS Receipt");
                            printManager.print("Ghazala POS Receipt", adapter, null);
                        } catch (Exception ex) {
                            Toast.makeText(activity,
                                    "Print service start nahi ho saki. Vendor printer SDK chahiye.",
                                    Toast.LENGTH_LONG).show();
                        }
                    }
                });

                String baseUrl = prefs.getString(PREF_SERVER_URL, "");
                if (baseUrl == null || baseUrl.trim().isEmpty()) {
                    baseUrl = "http://127.0.0.1/";
                }
                printView.loadDataWithBaseURL(baseUrl, html, "text/html", "UTF-8", null);
            } catch (Exception ex) {
                Toast.makeText(activity,
                        "Printer bridge ko device vendor SDK ki zarurat hai.",
                        Toast.LENGTH_LONG).show();
            }
        }
    }
}
