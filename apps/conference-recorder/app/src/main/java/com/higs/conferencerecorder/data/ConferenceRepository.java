package com.higs.conferencerecorder.data;

import com.higs.conferencerecorder.model.Conference;
import com.higs.conferencerecorder.model.ProgramItem;
import com.higs.conferencerecorder.model.SessionBlock;

import java.util.List;

public interface ConferenceRepository {
    List<Conference> conferences();

    Conference conference(String conferenceId);

    SessionBlock session(String conferenceId, String sessionId);

    ProgramItem item(String conferenceId, String itemId);

    List<ProgramItem> searchPosters(String conferenceId, String query);

    String loadedAssetName();
}
