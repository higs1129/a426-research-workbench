package com.higs.conferencerecorder.data;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public final class StorageTreeWriter {
    private final ContentResolver resolver;
    private final Uri rootDocument;

    public StorageTreeWriter(Context context, Uri treeUri) {
        resolver = context.getContentResolver();
        rootDocument = DocumentsContract.buildDocumentUriUsingTree(
                treeUri, DocumentsContract.getTreeDocumentId(treeUri));
    }

    public Uri ensureDirectory(String... pathSegments) throws IOException {
        Uri current = rootDocument;
        for (String rawSegment : pathSegments) {
            String segment = sanitizeSegment(rawSegment);
            Uri child = findChild(current, segment, DocumentsContract.Document.MIME_TYPE_DIR);
            if (child == null) {
                child = DocumentsContract.createDocument(
                        resolver,
                        current,
                        DocumentsContract.Document.MIME_TYPE_DIR,
                        segment);
            }
            if (child == null) throw new IOException("无法创建目录：" + segment);
            current = child;
        }
        return current;
    }

    public Uri writeNewFile(Uri parent, String fileName, String mimeType, String text)
            throws IOException {
        return writeNewFile(
                parent,
                fileName,
                mimeType,
                new java.io.ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)));
    }

    public Uri copyNewFile(Uri parent, String fileName, String mimeType, java.io.File source)
            throws IOException {
        try (InputStream input = new java.io.FileInputStream(source)) {
            return writeNewFile(parent, fileName, mimeType, input);
        }
    }

    private Uri writeNewFile(Uri parent, String fileName, String mimeType, InputStream input)
            throws IOException {
        String safeName = sanitizeFileName(fileName);
        if (findChild(parent, safeName, null) != null) {
            throw new IOException("文件已存在，为避免覆盖已停止：" + safeName);
        }
        Uri file = DocumentsContract.createDocument(resolver, parent, mimeType, safeName);
        if (file == null) throw new IOException("无法创建文件：" + safeName);
        try (OutputStream output = resolver.openOutputStream(file, "w")) {
            if (output == null) throw new IOException("无法打开文件：" + safeName);
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                output.write(buffer, 0, read);
            }
            output.flush();
        }
        return file;
    }

    private Uri findChild(Uri parent, String displayName, String requiredMimeType)
            throws IOException {
        String parentId = DocumentsContract.getDocumentId(parent);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(parent, parentId);
        String[] projection = {
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE
        };
        try (Cursor cursor = resolver.query(children, projection, null, null, null)) {
            if (cursor == null) return null;
            int idColumn = cursor.getColumnIndexOrThrow(
                    DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameColumn = cursor.getColumnIndexOrThrow(
                    DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            int mimeColumn = cursor.getColumnIndexOrThrow(
                    DocumentsContract.Document.COLUMN_MIME_TYPE);
            while (cursor.moveToNext()) {
                String name = cursor.getString(nameColumn);
                String mime = cursor.getString(mimeColumn);
                if (displayName.equals(name)
                        && (requiredMimeType == null || requiredMimeType.equals(mime))) {
                    return DocumentsContract.buildDocumentUriUsingTree(
                            parent, cursor.getString(idColumn));
                }
            }
            return null;
        } catch (RuntimeException error) {
            throw new IOException("无法读取所选目录", error);
        }
    }

    private static String sanitizeSegment(String value) {
        String safe = value == null ? "unknown" : value.trim();
        safe = safe.replaceAll("[\\\\/:*?\"<>|]", "_");
        return safe.isEmpty() ? "unknown" : safe;
    }

    private static String sanitizeFileName(String value) {
        return sanitizeSegment(value);
    }
}
