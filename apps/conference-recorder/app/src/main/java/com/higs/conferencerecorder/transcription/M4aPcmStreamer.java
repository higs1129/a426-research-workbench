package com.higs.conferencerecorder.transcription;

import android.media.AudioFormat;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;

import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.ByteBuffer;

final class M4aPcmStreamer {
    interface Cancellation {
        boolean isCancelled();
    }

    interface ProgressListener {
        void onProgress(int completedFiles, int totalFiles);
    }

    static final class AudioSpec {
        final int sampleRate;
        final int channelCount;

        AudioSpec(int sampleRate, int channelCount) {
            this.sampleRate = sampleRate;
            this.channelCount = channelCount;
        }
    }

    private M4aPcmStreamer() {
    }

    static AudioSpec probe(File[] files) throws IOException {
        if (files == null || files.length == 0) throw new IOException("没有可转写的录音");
        AudioSpec expected = null;
        for (File file : files) {
            AudioSpec current = probe(file);
            if (current.channelCount != 1) {
                throw new IOException("当前只支持单声道录音：" + file.getName());
            }
            if (expected == null) {
                expected = current;
            } else if (expected.sampleRate != current.sampleRate
                    || expected.channelCount != current.channelCount) {
                throw new IOException("多段录音的采样格式不一致");
            }
        }
        return expected;
    }

    static void stream(
            File[] files,
            OutputStream output,
            AudioSpec expected,
            Cancellation cancellation,
            ProgressListener progressListener) throws IOException {
        for (int index = 0; index < files.length; index++) {
            if (cancellation.isCancelled()) return;
            decodeOne(files[index], output, expected, cancellation);
            output.flush();
            progressListener.onProgress(index + 1, files.length);
        }
    }

    private static AudioSpec probe(File file) throws IOException {
        MediaExtractor extractor = new MediaExtractor();
        try {
            extractor.setDataSource(file.getAbsolutePath());
            int track = audioTrack(extractor);
            MediaFormat format = extractor.getTrackFormat(track);
            return new AudioSpec(
                    format.getInteger(MediaFormat.KEY_SAMPLE_RATE),
                    format.getInteger(MediaFormat.KEY_CHANNEL_COUNT));
        } finally {
            extractor.release();
        }
    }

    private static void decodeOne(
            File file,
            OutputStream output,
            AudioSpec expected,
            Cancellation cancellation) throws IOException {
        MediaExtractor extractor = new MediaExtractor();
        MediaCodec decoder = null;
        try {
            extractor.setDataSource(file.getAbsolutePath());
            int track = audioTrack(extractor);
            extractor.selectTrack(track);
            MediaFormat inputFormat = extractor.getTrackFormat(track);
            String mime = inputFormat.getString(MediaFormat.KEY_MIME);
            if (mime == null) throw new IOException("无法识别录音编码：" + file.getName());
            inputFormat.setInteger(MediaFormat.KEY_PCM_ENCODING, AudioFormat.ENCODING_PCM_16BIT);
            decoder = MediaCodec.createDecoderByType(mime);
            decoder.configure(inputFormat, null, null, 0);
            decoder.start();

            boolean inputEnded = false;
            boolean outputEnded = false;
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            while (!outputEnded && !cancellation.isCancelled()) {
                if (!inputEnded) {
                    int inputIndex = decoder.dequeueInputBuffer(10_000L);
                    if (inputIndex >= 0) {
                        ByteBuffer input = decoder.getInputBuffer(inputIndex);
                        if (input == null) throw new IOException("无法读取音频解码缓冲区");
                        int size = extractor.readSampleData(input, 0);
                        if (size < 0) {
                            decoder.queueInputBuffer(
                                    inputIndex, 0, 0, 0L, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputEnded = true;
                        } else {
                            decoder.queueInputBuffer(
                                    inputIndex, 0, size, extractor.getSampleTime(), 0);
                            extractor.advance();
                        }
                    }
                }

                int outputIndex = decoder.dequeueOutputBuffer(info, 10_000L);
                if (outputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    verifyOutputFormat(decoder.getOutputFormat(), expected, file);
                } else if (outputIndex >= 0) {
                    ByteBuffer buffer = decoder.getOutputBuffer(outputIndex);
                    if (buffer != null
                            && info.size > 0
                            && (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0) {
                        buffer.position(info.offset);
                        buffer.limit(info.offset + info.size);
                        byte[] chunk = new byte[Math.min(32 * 1024, info.size)];
                        while (buffer.hasRemaining() && !cancellation.isCancelled()) {
                            int length = Math.min(chunk.length, buffer.remaining());
                            buffer.get(chunk, 0, length);
                            output.write(chunk, 0, length);
                        }
                    }
                    outputEnded = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
                    decoder.releaseOutputBuffer(outputIndex, false);
                }
            }
        } catch (RuntimeException error) {
            throw new IOException("无法解码 " + file.getName() + "：" + safeMessage(error), error);
        } finally {
            if (decoder != null) {
                try {
                    decoder.stop();
                } catch (RuntimeException ignored) {
                    // Decoder may already be stopped after a device codec failure.
                }
                decoder.release();
            }
            extractor.release();
        }
    }

    private static void verifyOutputFormat(
            MediaFormat format, AudioSpec expected, File file) throws IOException {
        int sampleRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE);
        int channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
        int encoding = format.containsKey(MediaFormat.KEY_PCM_ENCODING)
                ? format.getInteger(MediaFormat.KEY_PCM_ENCODING)
                : AudioFormat.ENCODING_PCM_16BIT;
        if (sampleRate != expected.sampleRate || channels != expected.channelCount) {
            throw new IOException("解码后音频格式发生变化：" + file.getName());
        }
        if (encoding != AudioFormat.ENCODING_PCM_16BIT) {
            throw new IOException("系统解码器未输出 16 位 PCM：" + file.getName());
        }
    }

    private static int audioTrack(MediaExtractor extractor) throws IOException {
        for (int index = 0; index < extractor.getTrackCount(); index++) {
            MediaFormat format = extractor.getTrackFormat(index);
            String mime = format.getString(MediaFormat.KEY_MIME);
            if (mime != null && mime.startsWith("audio/")) return index;
        }
        throw new IOException("文件中没有可用音频轨道");
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName()
                : message;
    }
}
