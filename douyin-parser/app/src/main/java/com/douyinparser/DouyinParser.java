package com.douyinparser;

import android.util.Log;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import okhttp3.HttpUrl;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

/**
 * 抖音链接解析器
 * 支持解析抖音分享链接，提取视频信息
 */
public class DouyinParser {
    private static final String TAG = "DouyinParser";
    private final OkHttpClient httpClient;

    // 抖音链接正则匹配
    private static final Pattern DOUYIN_URL_PATTERN = Pattern.compile(
            "(https?://)?(www\\.|v\\.)?(douyin\\.com|iesdouyin\\.com)/[^\\s]+"
    );

    // 视频ID提取正则
    private static final Pattern VIDEO_ID_PATTERN = Pattern.compile(
            "(?:video|note|aweme)/(\\d+)"
    );
    private static final Pattern SHORT_URL_ID_PATTERN = Pattern.compile(
            "v\\.douyin\\.com/(\\w+)"
    );
    private static final Pattern MODAL_ID_PATTERN = Pattern.compile(
            "modal_id=(\\d+)"
    );

    public DouyinParser() {
        // 配置 OkHttp 客户端，不自动跟随重定向以便捕获短链接的跳转
        this.httpClient = new OkHttpClient.Builder()
                .followRedirects(false)
                .followSslRedirects(false)
                .build();
    }

    /**
     * 判断是否为抖音链接
     */
    public static boolean isDouyinUrl(String url) {
        if (url == null || url.isEmpty()) return false;
        return DOUYIN_URL_PATTERN.matcher(url).find();
    }

    /**
     * 从文本中提取抖音链接
     */
    public static String extractDouyinUrl(String text) {
        if (text == null || text.isEmpty()) return null;
        Matcher matcher = DOUYIN_URL_PATTERN.matcher(text);
        if (matcher.find()) {
            return matcher.group();
        }
        return null;
    }

    /**
     * 解析抖音链接，获取视频信息
     */
    public VideoInfo parse(String inputUrl) throws IOException {
        VideoInfo info = new VideoInfo();

        // 清理URL
        String url = inputUrl.trim();
        if (!url.startsWith("http")) {
            url = "https://" + url;
        }
        info.setOriginalUrl(url);

        Log.d(TAG, "解析链接: " + url);

        try {
            String resolvedUrl = resolveShortUrl(url);
            Log.d(TAG, "解析后URL: " + resolvedUrl);

            // 提取视频ID
            String videoId = extractVideoId(resolvedUrl);
            if (videoId != null) {
                info.setVideoId(videoId);
                Log.d(TAG, "视频ID: " + videoId);
            }

            // 获取页面信息
            fetchPageInfo(resolvedUrl, info);

            info.setSuccess(true);
        } catch (Exception e) {
            Log.e(TAG, "解析失败: " + e.getMessage(), e);
            info.setSuccess(false);
            info.setErrorMessage("解析失败: " + e.getMessage());
        }

        return info;
    }

    /**
     * 解析短链接，获取真实URL
     */
    private String resolveShortUrl(String url) throws IOException {
        String currentUrl = url;
        int maxRedirects = 10;

        for (int i = 0; i < maxRedirects; i++) {
            Request request = new Request.Builder()
                    .url(currentUrl)
                    .header("User-Agent", getMobileUserAgent())
                    .build();

            try (Response response = httpClient.newCall(request).execute()) {
                String location = response.header("Location");
                if (location != null && !location.isEmpty()) {
                    // 处理相对路径
                    if (location.startsWith("/")) {
                        try {
                            URI uri = new URI(currentUrl);
                            location = uri.getScheme() + "://" + uri.getHost() + location;
                        } catch (URISyntaxException e) {
                            Log.w(TAG, "URI解析失败: " + e.getMessage());
                        }
                    }
                    currentUrl = location;
                    Log.d(TAG, "重定向到: " + location);
                } else {
                    // 没有更多重定向，返回当前URL
                    break;
                }
            }
        }

        return currentUrl;
    }

    /**
     * 从URL中提取视频ID
     */
    private String extractVideoId(String url) {
        // 尝试 /video/123456 格式
        Matcher videoMatcher = VIDEO_ID_PATTERN.matcher(url);
        if (videoMatcher.find()) {
            return videoMatcher.group(1);
        }

        // 尝试 v.douyin.com/xxxxx 格式
        Matcher shortMatcher = SHORT_URL_ID_PATTERN.matcher(url);
        if (shortMatcher.find()) {
            return shortMatcher.group(1);
        }

        // 尝试 modal_id=123456 格式
        Matcher modalMatcher = MODAL_ID_PATTERN.matcher(url);
        if (modalMatcher.find()) {
            return modalMatcher.group(1);
        }

        return null;
    }

    /**
     * 获取页面信息（标题、作者、封面等）
     */
    private void fetchPageInfo(String url, VideoInfo info) throws IOException {
        Request request = new Request.Builder()
                .url(url)
                .header("User-Agent", getMobileUserAgent())
                .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                .header("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            // 如果还是重定向，先跟随
            String location = response.header("Location");
            if (location != null && !location.isEmpty()) {
                fetchPageInfo(location, info);
                return;
            }

            if (response.body() != null) {
                String html = response.body().string();
                parseHtml(html, info);
            }
        }
    }

    /**
     * 解析HTML，提取元数据
     */
    private void parseHtml(String html, VideoInfo info) {
        Document doc = Jsoup.parse(html);

        // 提取标题 - 多种来源
        String title = getMetaContent(doc, "og:title");
        if (title == null || title.isEmpty()) {
            title = getMetaContent(doc, "twitter:title");
        }
        if (title == null || title.isEmpty()) {
            title = doc.title();
        }
        info.setTitle(cleanText(title));

        // 提取描述
        String desc = getMetaContent(doc, "og:description");
        if (desc == null || desc.isEmpty()) {
            desc = getMetaContent(doc, "description");
        }
        if (desc == null || desc.isEmpty()) {
            desc = getMetaContent(doc, "twitter:description");
        }
        info.setDescription(cleanText(desc));

        // 提取封面图
        String cover = getMetaContent(doc, "og:image");
        if (cover == null || cover.isEmpty()) {
            cover = getMetaContent(doc, "twitter:image");
        }
        info.setCoverUrl(cover);

        // 提取视频URL
        String videoUrl = getMetaContent(doc, "og:video");
        if (videoUrl == null || videoUrl.isEmpty()) {
            videoUrl = getMetaContent(doc, "og:video:url");
        }
        if (videoUrl == null || videoUrl.isEmpty()) {
            videoUrl = getMetaContent(doc, "twitter:player:stream");
        }
        info.setVideoUrl(videoUrl);

        // 提取作者信息
        String author = getMetaContent(doc, "article:author");
        if (author == null || author.isEmpty()) {
            author = getMetaContent(doc, "author");
        }
        info.setAuthorName(cleanText(author));

        // 尝试从页面中提取更多信息
        // 抖音页面通常有 RENDER_DATA 或 SSR 数据
        extractFromScriptData(doc, info);
    }

    /**
     * 从页面脚本数据中提取信息
     */
    private void extractFromScriptData(Document doc, VideoInfo info) {
        Elements scripts = doc.select("script");
        for (Element script : scripts) {
            String content = script.html();
            if (content == null) continue;

            // 尝试从 JSON 数据中提取
            // 查找 "nickname"
            if (info.getAuthorName() == null || info.getAuthorName().isEmpty()) {
                Pattern nickPattern = Pattern.compile("\"nickname\"\\s*:\\s*\"([^\"]+)\"");
                Matcher m = nickPattern.matcher(content);
                if (m.find()) {
                    info.setAuthorName(m.group(1));
                }
            }

            // 查找 "sec_uid" (作者ID)
            if (info.getAuthorId() == null || info.getAuthorId().isEmpty()) {
                Pattern uidPattern = Pattern.compile("\"sec_uid\"\\s*:\\s*\"([^\"]+)\"");
                Matcher m = uidPattern.matcher(content);
                if (m.find()) {
                    info.setAuthorId(m.group(1));
                }
            }

            // 查找音乐标题
            if (info.getMusicTitle() == null || info.getMusicTitle().isEmpty()) {
                Pattern musicPattern = Pattern.compile("\"title\"\\s*:\\s*\"([^\"]+)\"\\s*,\\s*\"author\"");
                Matcher m = musicPattern.matcher(content);
                if (m.find()) {
                    info.setMusicTitle(m.group(1));
                }
            }
        }
    }

    /**
     * 获取 HTML meta 标签内容
     */
    private String getMetaContent(Document doc, String property) {
        // 先尝试 og: / twitter: 等 property 属性
        Element element = doc.selectFirst("meta[property=" + property + "]");
        if (element != null) {
            return element.attr("content");
        }

        // 再尝试 name 属性
        element = doc.selectFirst("meta[name=" + property + "]");
        if (element != null) {
            return element.attr("content");
        }

        return null;
    }

    /**
     * 清理文本（去除多余空白）
     */
    private String cleanText(String text) {
        if (text == null) return null;
        return text.replaceAll("\\s+", " ").trim();
    }

    /**
     * 获取移动端 User-Agent
     */
    private String getMobileUserAgent() {
        return "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36";
    }
}
