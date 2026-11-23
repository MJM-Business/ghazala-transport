package com.ghazalatransport.pos;

import android.app.Activity;
import android.app.AlertDialog;
import android.print.PrintManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.os.Bundle;
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

public class MainActivity extends Activity {
    private static final String PREFS = "ghazala_pos_prefs";
    private static final String PREF_SERVER_URL = "server_url";
    private WebView webView;
    private ProgressBar progress;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        buildUi();

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

    private final class PosBridge {
        private final Activity activity;

        PosBridge(Activity activity) {
            this.activity = activity;
        }

        @JavascriptInterface
        public void printHtml(String html, int paperWidthMm) {
            activity.runOnUiThread(() -> printWebContent());
        }

        @JavascriptInterface
        public void printWaybill(String awb, int paperWidthMm) {
            activity.runOnUiThread(() -> printWebContent());
        }

        private void printWebContent() {
            try {
                PrintManager printManager = (PrintManager) getSystemService(Context.PRINT_SERVICE);
                if (printManager == null) {
                    Toast.makeText(activity, "Android print service available nahi hai.", Toast.LENGTH_LONG).show();
                    return;
                }
                PrintDocumentAdapter adapter = webView.createPrintDocumentAdapter("Ghazala POS Receipt");
                printManager.print("Ghazala POS Receipt", adapter, null);
            } catch (Exception ex) {
                Toast.makeText(activity,
                        "Printer bridge ko device vendor SDK ki zarurat hai.",
                        Toast.LENGTH_LONG).show();
            }
        }
    }
}
