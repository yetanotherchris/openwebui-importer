CREATE TABLE
    "chat" (
        "id" VARCHAR(255) NOT NULL,
        "user_id" VARCHAR(255) NOT NULL,
        "title" TEXT NOT NULL NOT NULL,
        "share_id" VARCHAR(255),
        "archived" INTEGER NOT NULL,
        "created_at" DATETIME NOT NULL NOT NULL,
        "updated_at" DATETIME NOT NULL NOT NULL,
        chat JSON,
        pinned BOOLEAN,
        meta JSON DEFAULT '{}' NOT NULL,
        folder_id TEXT
    )
INSERT INTO
    "main"."chat" (
        "id",
        "user_id",
        "title",
        "share_id",
        "archived",
        "created_at",
        "updated_at",
        "chat",
        "pinned",
        "meta",
        "folder_id"
    )
VALUES
    (
        '96bdf63b-fccf-435a-b729-abf04ce7b42f',
        'd95194d2-9cef-4387-8ee4-b82eb2e1c637',
        '🧠 Goldwater Rule Ethics',
        NULL,
        0,
        1744577557,
        1744577567,
        '{"id": "", "title": "\ud83e\udde0 Goldwater Rule Ethics", "models": ["deepseek/deepseek-chat:free"], "params": {}, "history": {"messages": {"5ae90291-abf9-453f-9f7d-78f3753af40c": {"id": "5ae90291-abf9-453f-9f7d-78f3753af40c", "parentId": null, "childrenIds": ["a9436447-add3-4bd8-a25f-6ce54b73903c"], "role": "user", "content": "what was the ruling in the US called where you can''t diagnose a politician using psychiatry?", "timestamp": 1744577557, "models": ["deepseek/deepseek-chat:free"]}, "a9436447-add3-4bd8-a25f-6ce54b73903c": {"parentId": "5ae90291-abf9-453f-9f7d-78f3753af40c", "id": "a9436447-add3-4bd8-a25f-6ce54b73903c", "childrenIds": [], "role": "assistant", "content": "The principle you''re referring to is known as the **\"Goldwater Rule.\"** This ethical guideline is named after Barry Goldwater, the 1964 Republican presidential nominee, and it originates from a controversy involving psychiatrists.\n\n### Background:\nDuring the 1964 U.S. presidential campaign, *Fact* magazine published an article titled \"1,189 Psychiatrists Say Goldwater Is Psychologically Unfit to Be President!\" The article was based on a survey of psychiatrists, many of whom provided diagnoses of Goldwater without ever examining him personally. Goldwater later successfully sued the magazine for libel.\n\n### The Goldwater Rule:\nIn response to this incident, the American Psychiatric Association (APA) established the **Goldwater Rule** in 1973. This rule is part of the APA''s ethical guidelines and states that psychiatrists should not offer professional opinions about the mental health of public figures they have not personally examined and from whom they have not obtained proper consent to discuss their mental health.\n\n### Key Points:\n1. **No Diagnosis Without Examination:** Psychiatrists should not diagnose or speculate about the mental health of individuals they have not personally evaluated.\n2. **Public Figures:** This rule applies particularly to public figures, such as politicians, who are often the subject of public scrutiny.\n3. **Ethical Violation:** Violating the Goldwater Rule is considered a breach of professional ethics by the APA.\n\nThe Goldwater Rule is intended to protect the integrity of the psychiatric profession and prevent the misuse of psychiatry in political contexts.", "model": "deepseek/deepseek-chat:free", "modelName": "DeepSeek: DeepSeek V3 (free)", "modelIdx": 0, "userContext": null, "timestamp": 1744577557, "lastSentence": "3. Ethical Violation: Violating the Goldwater Rule is considered a breach of professional ethics by the APA.", "usage": {"prompt_tokens": 26, "completion_tokens": 310, "total_tokens": 336}, "done": true}}, "currentId": "a9436447-add3-4bd8-a25f-6ce54b73903c"}, "messages": [{"id": "5ae90291-abf9-453f-9f7d-78f3753af40c", "parentId": null, "childrenIds": ["a9436447-add3-4bd8-a25f-6ce54b73903c"], "role": "user", "content": "what was the ruling in the US called where you can''t diagnose a politician using psychiatry?", "timestamp": 1744577557, "models": ["deepseek/deepseek-chat:free"]}, {"parentId": "5ae90291-abf9-453f-9f7d-78f3753af40c", "id": "a9436447-add3-4bd8-a25f-6ce54b73903c", "childrenIds": [], "role": "assistant", "content": "The principle you''re referring to is known as the **\"Goldwater Rule.\"** This ethical guideline is named after Barry Goldwater, the 1964 Republican presidential nominee, and it originates from a controversy involving psychiatrists.\n\n### Background:\nDuring the 1964 U.S. presidential campaign, *Fact* magazine published an article titled \"1,189 Psychiatrists Say Goldwater Is Psychologically Unfit to Be President!\" The article was based on a survey of psychiatrists, many of whom provided diagnoses of Goldwater without ever examining him personally. Goldwater later successfully sued the magazine for libel.\n\n### The Goldwater Rule:\nIn response to this incident, the American Psychiatric Association (APA) established the **Goldwater Rule** in 1973. This rule is part of the APA''s ethical guidelines and states that psychiatrists should not offer professional opinions about the mental health of public figures they have not personally examined and from whom they have not obtained proper consent to discuss their mental health.\n\n### Key Points:\n1. **No Diagnosis Without Examination:** Psychiatrists should not diagnose or speculate about the mental health of individuals they have not personally evaluated.\n2. **Public Figures:** This rule applies particularly to public figures, such as politicians, who are often the subject of public scrutiny.\n3. **Ethical Violation:** Violating the Goldwater Rule is considered a breach of professional ethics by the APA.\n\nThe Goldwater Rule is intended to protect the integrity of the psychiatric profession and prevent the misuse of psychiatry in political contexts.", "model": "deepseek/deepseek-chat:free", "modelName": "DeepSeek: DeepSeek V3 (free)", "modelIdx": 0, "userContext": null, "timestamp": 1744577557, "lastSentence": "3. Ethical Violation: Violating the Goldwater Rule is considered a breach of professional ethics by the APA.", "usage": {"prompt_tokens": 26, "completion_tokens": 310, "total_tokens": 336}, "done": true}], "tags": [], "timestamp": 1744577557127, "files": []}',
        0,
        '{"tags": ["health", "ethics", "politics"]}',
        NULL
    );