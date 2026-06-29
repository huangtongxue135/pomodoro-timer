package com.douyinparser;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.method.LinkMovementMethod;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private EditText inputUrl;
    private Button parseButton;
    private Button pasteButton;
    private Button clearButton;
    private ProgressBar progressBar;
    private ScrollView resultScroll;
    private LinearLayout resultLayout;

    // 结果视图
    private ImageView coverImage;
    private TextView titleText;
    private TextView authorText;
    private TextView videoIdText;
    private TextView descriptionText;
    private TextView musicText;
    private TextView originalUrlText;
    private Button openInDouyinButton;
    private Button copyUrlButton;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        initViews();
        setupListeners();
        handleIncomingIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIncomingIntent(intent);
    }

    private void initViews() {
        inputUrl = findViewById(R.id.input_url);
        parseButton = findViewById(R.id.btn_parse);
        pasteButton = findViewById(R.id.btn_paste);
        clearButton = findViewById(R.id.btn_clear);
        progressBar = findViewById(R.id.progress_bar);
        resultScroll = findViewById(R.id.result_scroll);
        resultLayout = findViewById(R.id.result_layout);

        coverImage = findViewById(R.id.cover_image);
        titleText = findViewById(R.id.title_text);
        authorText = findViewById(R.id.author_text);
        videoIdText = findViewById(R.id.video_id_text);
        descriptionText = findViewById(R.id.description_text);
        musicText = findViewById(R.id.music_text);
        originalUrlText = findViewById(R.id.original_url_text);
        openInDouyinButton = findViewById(R.id.btn_open_in_douyin);
        copyUrlButton = findViewById(R.id.btn_copy_url);
    }

    private void setupListeners() {
        parseButton.setOnClickListener(v -> {
            String url = inputUrl.getText().toString().trim();
            if (url.isEmpty()) {
                Toast.makeText(this, "请输入抖音链接", Toast.LENGTH_SHORT).show();
                return;
            }
            parseUrl(url);
        });

        pasteButton.setOnClickListener(v -> {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null && clipboard.hasPrimaryClip()) {
                ClipData clipData = clipboard.getPrimaryClip();
                if (clipData != null && clipData.getItemCount() > 0) {
                    String text = clipData.getItemAt(0).getText().toString();
                    if (text != null) {
                        // 尝试从剪贴板文本中提取抖音链接
                        String douyinUrl = DouyinParser.extractDouyinUrl(text);
                        if (douyinUrl != null) {
                            inputUrl.setText(douyinUrl);
                        } else {
                            inputUrl.setText(text);
                        }
                        Toast.makeText(this, "已粘贴", Toast.LENGTH_SHORT).show();
                    }
                }
            }
        });

        clearButton.setOnClickListener(v -> {
            inputUrl.setText("");
            resultScroll.setVisibility(View.GONE);
            hideKeyboard();
        });

        // 输入框回车键直接解析
        inputUrl.setOnEditorActionListener((v, actionId, event) -> {
            String url = inputUrl.getText().toString().trim();
            if (!url.isEmpty()) {
                parseUrl(url);
            }
            return true;
        });
    }

    /**
     * 处理从其他App分享过来的链接
     */
    private void handleIncomingIntent(Intent intent) {
        if (intent != null && Intent.ACTION_SEND.equals(intent.getAction())) {
            String sharedText = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (sharedText != null) {
                String douyinUrl = DouyinParser.extractDouyinUrl(sharedText);
                if (douyinUrl != null) {
                    inputUrl.setText(douyinUrl);
                    parseUrl(douyinUrl);
                } else {
                    inputUrl.setText(sharedText);
                }
            }
        }
    }

    /**
     * 解析抖音链接
     */
    private void parseUrl(String url) {
        // 如果输入的是纯文本，尝试提取链接
        String douyinUrl = DouyinParser.extractDouyinUrl(url);
        if (douyinUrl == null) {
            Toast.makeText(this, "未检测到有效的抖音链接", Toast.LENGTH_SHORT).show();
            return;
        }

        showLoading(true);
        resultScroll.setVisibility(View.GONE);
        hideKeyboard();

        executor.execute(() -> {
            try {
                DouyinParser parser = new DouyinParser();
                VideoInfo info = parser.parse(douyinUrl);

                mainHandler.post(() -> {
                    showLoading(false);
                    if (info.isSuccess()) {
                        displayResult(info);
                    } else {
                        Toast.makeText(this, info.getErrorMessage(), Toast.LENGTH_LONG).show();
                        showSimpleResult(douyinUrl);
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    showLoading(false);
                    Toast.makeText(this, "解析出错: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    /**
     * 显示解析结果
     */
    private void displayResult(VideoInfo info) {
        resultScroll.setVisibility(View.VISIBLE);

        // 加载封面图
        if (info.getCoverUrl() != null && !info.getCoverUrl().isEmpty()) {
            loadCoverImage(info.getCoverUrl());
        } else {
            coverImage.setVisibility(View.GONE);
        }

        // 标题
        if (info.getTitle() != null && !info.getTitle().isEmpty()) {
            titleText.setText(info.getTitle());
            titleText.setVisibility(View.VISIBLE);
        } else {
            titleText.setVisibility(View.GONE);
        }

        // 作者
        if (info.getAuthorName() != null && !info.getAuthorName().isEmpty()) {
            authorText.setText("👤 作者: " + info.getAuthorName());
            authorText.setVisibility(View.VISIBLE);
        } else {
            authorText.setVisibility(View.GONE);
        }

        // 视频ID
        if (info.getVideoId() != null && !info.getVideoId().isEmpty()) {
            videoIdText.setText("🆔 视频ID: " + info.getVideoId());
            videoIdText.setVisibility(View.VISIBLE);
        } else {
            videoIdText.setVisibility(View.GONE);
        }

        // 描述
        if (info.getDescription() != null && !info.getDescription().isEmpty()) {
            descriptionText.setText("📝 " + info.getDescription());
            descriptionText.setVisibility(View.VISIBLE);
        } else {
            descriptionText.setVisibility(View.GONE);
        }

        // 音乐
        if (info.getMusicTitle() != null && !info.getMusicTitle().isEmpty()) {
            musicText.setText("🎵 音乐: " + info.getMusicTitle());
            musicText.setVisibility(View.VISIBLE);
        } else {
            musicText.setVisibility(View.GONE);
        }

        // 原始链接（可点击）
        originalUrlText.setMovementMethod(LinkMovementMethod.getInstance());
        originalUrlText.setText("🔗 原始链接: " + info.getOriginalUrl());

        // 在抖音中打开按钮
        String videoId = info.getVideoId();
        openInDouyinButton.setOnClickListener(v -> openInDouyin(videoId, info.getOriginalUrl()));
        openInDouyinButton.setVisibility(View.VISIBLE);

        // 复制链接按钮
        copyUrlButton.setOnClickListener(v -> {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            ClipData clip = ClipData.newPlainText("douyin_url", info.getOriginalUrl());
            clipboard.setPrimaryClip(clip);
            Toast.makeText(this, "链接已复制到剪贴板", Toast.LENGTH_SHORT).show();
        });
        copyUrlButton.setVisibility(View.VISIBLE);
    }

    /**
     * 显示简单结果（解析不完全时）
     */
    private void showSimpleResult(String url) {
        resultScroll.setVisibility(View.VISIBLE);
        coverImage.setVisibility(View.GONE);
        titleText.setVisibility(View.GONE);
        authorText.setVisibility(View.GONE);
        videoIdText.setVisibility(View.GONE);
        descriptionText.setVisibility(View.GONE);
        musicText.setVisibility(View.GONE);

        originalUrlText.setText("已检测到抖音链接:\n" + url);
        originalUrlText.setVisibility(View.VISIBLE);

        openInDouyinButton.setOnClickListener(v -> openInDouyin(null, url));
        openInDouyinButton.setVisibility(View.VISIBLE);
        copyUrlButton.setVisibility(View.VISIBLE);
    }

    /**
     * 加载封面图片
     */
    private void loadCoverImage(String imageUrl) {
        executor.execute(() -> {
            try {
                URL url = new URL(imageUrl);
                HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                connection.setRequestProperty("User-Agent",
                        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36");
                connection.setConnectTimeout(10000);
                connection.setReadTimeout(10000);
                connection.connect();

                InputStream input = connection.getInputStream();
                Bitmap bitmap = BitmapFactory.decodeStream(input);
                input.close();

                if (bitmap != null) {
                    mainHandler.post(() -> {
                        coverImage.setImageBitmap(bitmap);
                        coverImage.setVisibility(View.VISIBLE);
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> coverImage.setVisibility(View.GONE));
            }
        });
    }

    /**
     * 在抖音App中打开
     */
    private void openInDouyin(String videoId, String url) {
        try {
            Intent intent;
            if (videoId != null && !videoId.isEmpty()) {
                // 尝试用抖音的 scheme 打开
                intent = new Intent(Intent.ACTION_VIEW,
                        Uri.parse("snssdk1128://aweme/detail/" + videoId));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            } else {
                // 用网页打开
                intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            }

            // 先尝试用抖音App打开
            try {
                startActivity(intent);
                return;
            } catch (Exception e) {
                // 抖音未安装，用浏览器打开
            }

            // 降级为浏览器打开
            Intent browserIntent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            startActivity(browserIntent);
        } catch (Exception e) {
            Toast.makeText(this, "无法打开链接", Toast.LENGTH_SHORT).show();
        }
    }

    private void showLoading(boolean show) {
        progressBar.setVisibility(show ? View.VISIBLE : View.GONE);
        parseButton.setEnabled(!show);
    }

    private void hideKeyboard() {
        View view = getCurrentFocus();
        if (view != null) {
            InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            imm.hideSoftInputFromWindow(view.getWindowToken(), 0);
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
