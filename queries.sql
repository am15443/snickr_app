-- =============================================================
-- Query (1): Create a new user account
-- =============================================================
INSERT INTO users (email, username, nickname, password_hash)
VALUES ('alice@example.com', 'alice', 'Ali', crypt('password123', gen_salt('bf')));


-- =============================================================
-- Query (2): Create a new public channel inside a workspace
--            by a particular user (checks user is authorized)
-- Only proceeds if user_id=1 (Alice) is a member of workspace_id=1 (Acme Corp)
-- =============================================================
INSERT INTO channels (workspace_id, name, type, creator_id)
SELECT 1, 'announcements', 'public', 1
WHERE EXISTS (
    SELECT 1 FROM workspace_members
    WHERE workspace_id = 1 AND user_id = 1
);

INSERT INTO channel_members (channel_id, user_id)
SELECT channel_id, 1
FROM channels
WHERE name = 'announcements' AND workspace_id = 1;

-- =============================================================
-- Query (3): For each workspace, list all current administrators
-- =============================================================
SELECT w.name AS workspace, u.username, u.email
FROM workspace_members wm
JOIN workspaces w ON w.workspace_id = wm.workspace_id
JOIN users u ON u.user_id = wm.user_id
WHERE wm.is_admin = TRUE
ORDER BY w.name, u.username;


-- =============================================================
-- Query (4): For each public channel in a given workspace,
--            list the number of users invited more than 5 days
--            ago that have not yet joined
-- =============================================================
SELECT c.name AS channel, COUNT(*) AS pending_count
FROM channel_invitations ci
JOIN channels c ON c.channel_id = ci.channel_id
WHERE c.workspace_id = 1
  AND c.type = 'public'
  AND ci.accepted_at IS NULL
  AND ci.invited_at < NOW() - INTERVAL '5 days'
GROUP BY c.name;


-- =============================================================
-- Query (5): For a particular channel, list all messages
--            in chronological order
-- =============================================================
SELECT u.username, m.body, m.posted_at
FROM messages m
JOIN users u ON u.user_id = m.user_id
WHERE m.channel_id = 1
ORDER BY m.posted_at ASC;


-- =============================================================
-- Query (6): For a particular user, list all messages
--            they have posted in any channel
-- =============================================================
SELECT c.name AS channel, m.body, m.posted_at
FROM messages m
JOIN channels c ON c.channel_id = m.channel_id
WHERE m.user_id = 2
ORDER BY m.posted_at DESC;


-- =============================================================
-- Query (7): For a particular user, list all messages accessible
--            to that user containing the keyword "perpendicular"
--            (user must be a member of both the workspace
--            and the channel where the message occurs)
-- =============================================================
SELECT c.name AS channel, w.name AS workspace, m.body, m.posted_at
FROM messages m
JOIN channels c ON c.channel_id = m.channel_id
JOIN workspaces w ON w.workspace_id = c.workspace_id
-- User must be a workspace member
JOIN workspace_members wm ON wm.workspace_id = c.workspace_id AND wm.user_id = 2
-- User must be a channel member
JOIN channel_members cm ON cm.channel_id = m.channel_id AND cm.user_id = 2
WHERE m.body LIKE '%perpendicular%'
ORDER BY m.posted_at DESC;