package com.higs.conferencerecorder.recording;

import android.annotation.SuppressLint;

import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import android.media.MediaRecorder;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;

/**
 * Owns the microphone once, writes an AAC/M4A recording, and exposes copies of the same PCM
 * frames to optional consumers such as live speech recognition.
 */
public final class PcmAacRecorder implements AutoCloseable {
    public interface Listener {
        void onPcm(byte[] pcm, int length, int sampleRate);

        void onFailure(String message);
    }

    private static final String MIME_TYPE = MediaFormat.MIMETYPE_AUDIO_AAC;
    private static final int SAMPLE_RATE = 16_000;
    private static final int CHANNEL_COUNT = 1;
    private static final int BYTES_PER_SAMPLE = 2;
    private static final int BIT_RATE = 64_000;
    private static final long CODEC_TIMEOUT_US = 10_000L;

    private final Object stateLock = new Object();
    private final Listener listener;

    private AudioRecord audioRecord;
    private MediaCodec codec;
    private MediaMuxer muxer;
    private Thread captureThread;
    private volatile boolean stopRequested;
    private volatile boolean paused;
    private volatile boolean closed;
    private int muxerTrack = -1;
    private boolean muxerStarted;
    private long submittedSamples;

    public PcmAacRecorder(Listener listener) {
        this.listener = listener;
    }

    public int sampleRate() {
        return SAMPLE_RATE;
    }

    @SuppressLint("MissingPermission") // PackageActivity checks RECORD_AUDIO immediately before start.
    public void start(File outputFile) throws IOException {
        if (outputFile == null) throw new IOException("录音输出文件为空");
        int minimumBuffer = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT);
        if (minimumBuffer <= 0) throw new IOException("手机不支持 16 kHz 单声道录音");

        int audioBufferSize = Math.max(minimumBuffer * 2, 16 * 1024);
        try {
            audioRecord = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    audioBufferSize);
            if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
                throw new IOException("无法初始化手机麦克风");
            }

            MediaFormat format = MediaFormat.createAudioFormat(
                    MIME_TYPE, SAMPLE_RATE, CHANNEL_COUNT);
            format.setInteger(
                    MediaFormat.KEY_AAC_PROFILE,
                    MediaCodecInfo.CodecProfileLevel.AACObjectLC);
            format.setInteger(MediaFormat.KEY_BIT_RATE, BIT_RATE);
            format.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, audioBufferSize);
            codec = MediaCodec.createEncoderByType(MIME_TYPE);
            codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
            codec.start();

            muxer = new MediaMuxer(
                    outputFile.getAbsolutePath(),
                    MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
            audioRecord.startRecording();
            if (audioRecord.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) {
                throw new IOException("麦克风没有进入录音状态");
            }
            captureThread = new Thread(this::captureLoop, "conference-pcm-aac-recorder");
            captureThread.start();
        } catch (IOException | RuntimeException error) {
            releaseResources();
            if (error instanceof IOException) throw (IOException) error;
            throw new IOException("无法启动录音：" + safeMessage(error), error);
        }
    }

    public void pause() throws IOException {
        synchronized (stateLock) {
            if (closed || stopRequested || paused) return;
            paused = true;
            try {
                audioRecord.stop();
            } catch (IllegalStateException error) {
                paused = false;
                throw new IOException("无法暂停麦克风：" + safeMessage(error), error);
            }
        }
    }

    public void resume() throws IOException {
        synchronized (stateLock) {
            if (closed || stopRequested || !paused) return;
            try {
                audioRecord.startRecording();
                if (audioRecord.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) {
                    throw new IOException("麦克风没有恢复录音");
                }
                paused = false;
                stateLock.notifyAll();
            } catch (IllegalStateException error) {
                throw new IOException("无法继续麦克风录音：" + safeMessage(error), error);
            }
        }
    }

    /** Stops capture and waits for the AAC end-of-stream to be written. */
    public void stop() throws IOException {
        Thread thread;
        synchronized (stateLock) {
            if (closed) return;
            stopRequested = true;
            paused = false;
            stateLock.notifyAll();
            thread = captureThread;
            try {
                if (audioRecord != null
                        && audioRecord.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) {
                    audioRecord.stop();
                }
            } catch (IllegalStateException ignored) {
                // The capture loop may already have stopped the AudioRecord instance.
            }
        }
        if (thread != null && thread != Thread.currentThread()) {
            try {
                thread.join(3_000L);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
                throw new IOException("等待录音文件结束时被中断", error);
            }
            if (thread.isAlive()) throw new IOException("录音编码器未能及时结束");
        }
        closed = true;
    }

    private void captureLoop() {
        byte[] pcm = new byte[3_200]; // 100 ms at 16 kHz mono PCM16.
        try {
            while (!stopRequested) {
                synchronized (stateLock) {
                    while (paused && !stopRequested) stateLock.wait();
                }
                if (stopRequested) break;
                int read = audioRecord.read(pcm, 0, pcm.length, AudioRecord.READ_BLOCKING);
                if (read > 0) {
                    queuePcm(pcm, read);
                    drainEncoder(false);
                    if (listener != null) listener.onPcm(pcm, read, SAMPLE_RATE);
                } else if (!paused && !stopRequested) {
                    throw new IOException("麦克风读取失败（" + read + "）");
                }
            }
            queueEndOfStream();
            drainEncoder(true);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            notifyFailure("录音线程被中断");
        } catch (IOException | RuntimeException error) {
            if (!stopRequested) notifyFailure("录音编码失败：" + safeMessage(error));
        } finally {
            releaseResources();
            closed = true;
        }
    }

    private void queuePcm(byte[] source, int length) throws IOException {
        int offset = 0;
        int idleCount = 0;
        while (offset < length) {
            int inputIndex = codec.dequeueInputBuffer(CODEC_TIMEOUT_US);
            if (inputIndex < 0) {
                drainEncoder(false);
                if (++idleCount >= 100) throw new IOException("AAC 编码器长时间没有输入缓冲区");
                continue;
            }
            idleCount = 0;
            ByteBuffer input = codec.getInputBuffer(inputIndex);
            if (input == null) throw new IOException("AAC 编码器没有输入缓冲区");
            input.clear();
            int count = Math.min(input.remaining(), length - offset);
            input.put(source, offset, count);
            long presentationTimeUs = submittedSamples * 1_000_000L / SAMPLE_RATE;
            submittedSamples += count / (CHANNEL_COUNT * BYTES_PER_SAMPLE);
            codec.queueInputBuffer(inputIndex, 0, count, presentationTimeUs, 0);
            offset += count;
        }
    }

    private void queueEndOfStream() throws IOException {
        int idleCount = 0;
        while (true) {
            int inputIndex = codec.dequeueInputBuffer(CODEC_TIMEOUT_US);
            if (inputIndex < 0) {
                drainEncoder(false);
                if (++idleCount >= 100) throw new IOException("AAC 编码器无法结束文件");
                continue;
            }
            long presentationTimeUs = submittedSamples * 1_000_000L / SAMPLE_RATE;
            codec.queueInputBuffer(
                    inputIndex,
                    0,
                    0,
                    presentationTimeUs,
                    MediaCodec.BUFFER_FLAG_END_OF_STREAM);
            return;
        }
    }

    private void drainEncoder(boolean waitForEnd) throws IOException {
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        int idleCount = 0;
        while (true) {
            int outputIndex = codec.dequeueOutputBuffer(
                    info, waitForEnd ? CODEC_TIMEOUT_US : 0L);
            if (outputIndex == MediaCodec.INFO_TRY_AGAIN_LATER) {
                if (!waitForEnd || ++idleCount >= 100) return;
                continue;
            }
            if (outputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                if (muxerStarted) throw new IOException("AAC 编码格式重复变化");
                muxerTrack = muxer.addTrack(codec.getOutputFormat());
                muxer.start();
                muxerStarted = true;
                continue;
            }
            if (outputIndex < 0) continue;

            ByteBuffer output = codec.getOutputBuffer(outputIndex);
            if (output == null) throw new IOException("AAC 编码器没有输出缓冲区");
            if ((info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0) info.size = 0;
            if (info.size > 0) {
                if (!muxerStarted) throw new IOException("M4A 封装器尚未启动");
                output.position(info.offset);
                output.limit(info.offset + info.size);
                muxer.writeSampleData(muxerTrack, output, info);
            }
            boolean end = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
            codec.releaseOutputBuffer(outputIndex, false);
            if (end) return;
        }
    }

    private void notifyFailure(String message) {
        if (listener != null) listener.onFailure(message);
    }

    private void releaseResources() {
        if (audioRecord != null) {
            try {
                if (audioRecord.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) {
                    audioRecord.stop();
                }
            } catch (IllegalStateException ignored) {
            }
            audioRecord.release();
            audioRecord = null;
        }
        if (codec != null) {
            try {
                codec.stop();
            } catch (IllegalStateException ignored) {
            }
            codec.release();
            codec = null;
        }
        if (muxer != null) {
            if (muxerStarted) {
                try {
                    muxer.stop();
                } catch (IllegalStateException ignored) {
                }
            }
            muxer.release();
            muxer = null;
        }
    }

    @Override
    public void close() {
        try {
            stop();
        } catch (IOException ignored) {
            releaseResources();
        }
    }

    private static String safeMessage(Exception error) {
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
                ? error.getClass().getSimpleName()
                : message;
    }
}
