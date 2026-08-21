package com.higs.conferencerecorder.data;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.provider.DocumentsContract;

public final class StorageTargetStore {
    private static final String FILE_NAME = "storage_target";
    private static final String KEY_TREE_URI = "tree_uri";
    private static final String KEY_DISPLAY_PATH = "display_path";
    private static final String KEY_LAST_EXPORT = "last_export";

    private StorageTargetStore() {
    }

    public static void saveTarget(Context context, Uri treeUri) {
        preferences(context).edit()
                .putString(KEY_TREE_URI, treeUri.toString())
                .putString(KEY_DISPLAY_PATH, describeTree(treeUri))
                .apply();
    }

    public static Uri targetUri(Context context) {
        String value = preferences(context).getString(KEY_TREE_URI, "");
        return value == null || value.isEmpty() ? null : Uri.parse(value);
    }

    public static boolean isConfigured(Context context) {
        Uri target = targetUri(context);
        if (target == null) return false;
        return context.getContentResolver().getPersistedUriPermissions().stream()
                .anyMatch(permission -> permission.getUri().equals(target)
                        && permission.isWritePermission());
    }

    public static String displayPath(Context context) {
        return preferences(context).getString(KEY_DISPLAY_PATH, "尚未选择");
    }

    public static void saveLastExport(Context context, String displayPath) {
        preferences(context).edit().putString(KEY_LAST_EXPORT, displayPath).apply();
    }

    public static String lastExport(Context context) {
        return preferences(context).getString(KEY_LAST_EXPORT, "暂无导出记录");
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE);
    }

    private static String describeTree(Uri uri) {
        try {
            String documentId = DocumentsContract.getTreeDocumentId(uri);
            int separator = documentId.indexOf(':');
            if (separator >= 0) {
                String volume = documentId.substring(0, separator);
                String path = documentId.substring(separator + 1);
                String prefix = "primary".equals(volume) ? "内部存储" : volume;
                return path.isEmpty() ? prefix : prefix + "/" + path;
            }
            return documentId;
        } catch (RuntimeException ignored) {
            return uri.toString();
        }
    }
}
