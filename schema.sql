-- SCHEMA CREATION--

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    nickname      VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE workspaces (
    workspace_id SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    description  TEXT,
    creator_id   INTEGER NOT NULL REFERENCES users(user_id),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Tracks all current workspace members -- 
CREATE TABLE workspace_members (
    workspace_id INTEGER NOT NULL REFERENCES workspaces(workspace_id),
    user_id      INTEGER NOT NULL REFERENCES users(user_id),
    is_admin     BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);

-- Tracks pending and accepted invitations to workspaces -- 
CREATE TABLE workspace_invitations (
    invitation_id   SERIAL PRIMARY KEY,
    workspace_id    INTEGER NOT NULL REFERENCES workspaces(workspace_id),
    invited_user_id INTEGER NOT NULL REFERENCES users(user_id),
    invited_by      INTEGER NOT NULL REFERENCES users(user_id),
    invited_at      TIMESTAMPTZ DEFAULT NOW(),
    accepted_at     TIMESTAMPTZ  -- if NULL invitation is not yet accepted
);

-- type: 'public', 'private', or 'direct'
CREATE TABLE channels (
    channel_id   SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(workspace_id),
    name         VARCHAR(100) NOT NULL,
    type         VARCHAR(10) NOT NULL CHECK (type IN ('public','private','direct')),
    creator_id   INTEGER NOT NULL REFERENCES users(user_id),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (workspace_id, name)
);

-- Tracks current channel members
CREATE TABLE channel_members (
    channel_id INTEGER NOT NULL REFERENCES channels(channel_id),
    user_id    INTEGER NOT NULL REFERENCES users(user_id),
    joined_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (channel_id, user_id)
);

-- Tracks pending and accepted invitations to channels
CREATE TABLE channel_invitations (
    invitation_id   SERIAL PRIMARY KEY,
    channel_id      INTEGER NOT NULL REFERENCES channels(channel_id),
    invited_user_id INTEGER NOT NULL REFERENCES users(user_id),
    invited_by      INTEGER NOT NULL REFERENCES users(user_id),
    invited_at      TIMESTAMPTZ DEFAULT NOW(),
    accepted_at     TIMESTAMPTZ  -- if NULL invitation is not yet accepted
);

CREATE TABLE messages (
    message_id SERIAL PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES channels(channel_id),
    user_id    INTEGER NOT NULL REFERENCES users(user_id),
    body       TEXT NOT NULL,
    posted_at  TIMESTAMPTZ DEFAULT NOW()
);
