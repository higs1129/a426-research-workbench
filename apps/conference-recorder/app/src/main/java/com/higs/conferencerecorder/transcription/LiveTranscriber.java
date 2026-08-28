package com.higs.conferencerecorder.transcription;

import java.io.IOException;

public interface LiveTranscriber extends AutoCloseable {
    interface Listener {
        void onStatus(String status);

        void onPartial(String text);

        void onSegment(String text);

        void onCompleted();

        void onFailed(String message, String lastPartial);
    }

    void start(int sampleRate) throws IOException;

    void offer(byte[] pcm, int length);

    void finish();

    @Override
    void close();
}
