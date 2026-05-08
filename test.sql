-- =============================================================
-- Test data for Query (1): Create a new user account
-- Tests that users can be inserted with email, username,
-- nickname, and password hash
-- =============================================================
INSERT INTO users (email, username, nickname, password_hash)
VALUES
  ('alice@example.com', 'alice', 'Ali', 'hash1'),
  ('bob@example.com',   'bob',   'Bob', 'hash2'),
  ('carol@example.com', 'carol', 'Car', 'hash3');

-- =============================================================
-- Test data for Query (2): Create a new public channel
-- Workspace must exist before a channel can be created
-- Alice (user_id=1) is the creator and becomes workspace admin
-- =============================================================
INSERT INTO workspaces (name, description, creator_id)
VALUES ('Acme Corp', 'Company workspace', 1);

-- =============================================================
-- Test data for Query (3): List all administrators per workspace
-- Alice (user_id=1) is admin, Bob (user_id=2) is a regular member
-- Query (3) should return only Alice as the administrator
-- =============================================================
INSERT INTO workspace_members (workspace_id, user_id, is_admin)
VALUES (1, 1, TRUE), (1, 2, FALSE);

-- =============================================================
-- Test data for Query (4): Users invited more than 5 days ago
-- that have not yet joined
-- Carol (user_id=3) was invited 6 days ago and has not accepted
-- (accepted_at is NULL), so Query (4) should return Carol
-- =============================================================
INSERT INTO workspace_invitations (workspace_id, invited_user_id, invited_by, invited_at)
VALUES (1, 3, 1, NOW() - INTERVAL '6 days');

-- =============================================================
-- Test data for Queries (2), (4), (5), (6), (7):
-- Three channels are created to test different channel types
-- and access restrictions:
--   general (public)     -- accessible to Alice and Bob
--   leadership (private) -- accessible to Alice only
--   alice-bob (direct)   -- accessible to Alice and Bob only
-- =============================================================
INSERT INTO channels (workspace_id, name, type, creator_id)
VALUES
  (1, 'general',    'public',  1),
  (1, 'leadership', 'private', 1),
  (1, 'alice-bob',  'direct',  1);

INSERT INTO channel_invitations (channel_id, invited_user_id, invited_by, invited_at)
VALUES (1, 3, 1, NOW() - INTERVAL '6 days');

-- =============================================================
-- Test data for Queries (5), (6), (7):
-- Alice and Bob are members of general (channel_id=1)
-- Alice is the only member of leadership (channel_id=2)
-- Alice and Bob are members of alice-bob (channel_id=3)
-- This tests that Query (7) correctly restricts results
-- to channels the user is a member of
-- =============================================================
INSERT INTO channel_members (channel_id, user_id)
VALUES (1, 1), (1, 2), (2, 1), (3, 1), (3, 2);

-- =============================================================
-- Test data for Queries (5), (6), (7):
-- Three messages are inserted across two channels:
--   "Welcome everyone!" posted by Alice in general
--   "The lines are perpendicular..." posted by Bob in general
--   "Leadership only message" posted by Alice in leadership
-- Query (5) should return all messages in a given channel
-- Query (6) should return all messages by a given user
-- Query (7) should find the perpendicular message only in
-- channels the querying user is a member of -- Bob should
-- not see the leadership message even though it exists
-- =============================================================
INSERT INTO messages (channel_id, user_id, body)
VALUES
  (1, 1, 'Welcome everyone!'),
  (1, 2, 'The lines are perpendicular to each other.'),
  (2, 1, 'Leadership only message.');