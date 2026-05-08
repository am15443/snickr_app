from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
import psycopg2.extras
import bcrypt
from dotenv import load_dotenv
import os
load_dotenv()


app = Flask(__name__)
app.secret_key = 'snickr_secret_key_change_in_production'

# ------------------------------------------------------------------
# Database connection
# ------------------------------------------------------------------

def get_db():
     conn = psycopg2.connect(
        dbname="snickr",
        user="postgres",
        password=os.getenv('DB_PASSWORD'), #password protected in .env file
        host="localhost"
    )
    conn.autocommit = False
    return conn


def require_login():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return None


# ------------------------------------------------------------------
# Auth routes
# ------------------------------------------------------------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('workspaces'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '')

        if not email or not username or not password:
            flash('Email, username, and password are required.', 'error')
            return render_template('register.html')

        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (email, username, nickname, password_hash) VALUES (%s, %s, %s, %s)",
                (email, username, nickname, pw_hash)
            )
            conn.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            flash('Email or username already taken.', 'error')
        finally:
            cur.close()
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            session['user_id']  = int(user['user_id'])
            session['username'] = user['username']
            session['nickname'] = user['nickname'] or user['username']
            return redirect(url_for('workspaces'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ------------------------------------------------------------------
# Workspaces
# ------------------------------------------------------------------

@app.route('/workspaces')
def workspaces():
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT w.workspace_id, w.name, w.description, w.created_at,
               wm.is_admin
        FROM workspaces w
        JOIN workspace_members wm ON wm.workspace_id = w.workspace_id
        WHERE wm.user_id = %s
        ORDER BY w.name
    """, (session['user_id'],))
    my_workspaces = cur.fetchall()

    # Pending workspace invitations
    cur.execute("""
        SELECT wi.invitation_id, w.name AS workspace_name, u.username AS invited_by_name
        FROM workspace_invitations wi
        JOIN workspaces w ON w.workspace_id = wi.workspace_id
        JOIN users u ON u.user_id = wi.invited_by
        WHERE wi.invited_user_id = %s AND wi.accepted_at IS NULL
    """, (session['user_id'],))
    pending_invites = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('workspaces.html', workspaces=my_workspaces, pending_invites=pending_invites)


@app.route('/workspaces/new', methods=['GET', 'POST'])
def new_workspace():
    redir = require_login()
    if redir: return redir

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Workspace name is required.', 'error')
            return render_template('new_workspace.html')

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO workspaces (name, description, creator_id) VALUES (%s, %s, %s) RETURNING workspace_id",
                (name, description, session['user_id'])
            )
            workspace_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, is_admin) VALUES (%s, %s, TRUE)",
                (workspace_id, session['user_id'])
            )
            conn.commit()
            return redirect(url_for('workspace', workspace_id=workspace_id))
        except Exception:
            conn.rollback()
            flash('Error creating workspace.', 'error')
        finally:
            cur.close()
            conn.close()

    return render_template('new_workspace.html')


@app.route('/workspaces/<int:workspace_id>')
def workspace(workspace_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Check membership
    cur.execute("SELECT * FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, session['user_id']))
    membership = cur.fetchone()
    if not membership:
        flash('You are not a member of this workspace.', 'error')
        return redirect(url_for('workspaces'))

    cur.execute("SELECT * FROM workspaces WHERE workspace_id = %s", (workspace_id,))
    ws = cur.fetchone()

    # Channels visible to this user
    cur.execute("""
        SELECT c.channel_id, c.name, c.type,
               EXISTS(SELECT 1 FROM channel_members cm WHERE cm.channel_id = c.channel_id AND cm.user_id = %s) AS is_member
        FROM channels c
        WHERE c.workspace_id = %s
          AND (
            c.type = 'public'
            OR EXISTS(SELECT 1 FROM channel_members cm WHERE cm.channel_id = c.channel_id AND cm.user_id = %s)
          )
        ORDER BY c.type, c.name
    """, (session['user_id'], workspace_id, session['user_id']))
    channels = cur.fetchall()

    # Admins
    cur.execute("""
        SELECT u.username FROM workspace_members wm
        JOIN users u ON u.user_id = wm.user_id
        WHERE wm.workspace_id = %s AND wm.is_admin = TRUE
    """, (workspace_id,))
    admins = cur.fetchall()

    # Pending channel invitations for this user in this workspace
    cur.execute("""
        SELECT ci.invitation_id, c.name AS channel_name, c.channel_id
        FROM channel_invitations ci
        JOIN channels c ON c.channel_id = ci.channel_id
        WHERE ci.invited_user_id = %s AND ci.accepted_at IS NULL AND c.workspace_id = %s
    """, (session['user_id'], workspace_id))
    channel_invites = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('workspace.html', ws=ws, channels=channels,
                           membership=membership, admins=admins,
                           channel_invites=channel_invites)


@app.route('/workspaces/<int:workspace_id>/invite', methods=['GET', 'POST'])
def invite_to_workspace(workspace_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Only admins can invite
    cur.execute("SELECT is_admin FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, session['user_id']))
    mem = cur.fetchone()
    if not mem or not mem['is_admin']:
        flash('Only admins can invite users.', 'error')
        return redirect(url_for('workspace', workspace_id=workspace_id))

    cur.execute("SELECT * FROM workspaces WHERE workspace_id = %s", (workspace_id,))
    ws = cur.fetchone()

    if request.method == 'POST':
        invitee_username = request.form.get('username', '').strip()
        cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur2.execute("SELECT user_id FROM users WHERE username = %s", (invitee_username,))
        invitee = cur2.fetchone()

        if not invitee:
            flash('User not found.', 'error')
        else:
            try:
                cur2.execute("""
                    INSERT INTO workspace_invitations (workspace_id, invited_user_id, invited_by)
                    VALUES (%s, %s, %s)
                """, (workspace_id, invitee['user_id'], session['user_id']))
                conn.commit()
                flash(f'Invitation sent to {invitee_username}.', 'success')
            except Exception:
                conn.rollback()
                flash('Could not send invitation (already invited?).', 'error')
            cur2.close()

    cur.close()
    conn.close()
    return render_template('invite_workspace.html', ws=ws, workspace_id=workspace_id)


@app.route('/workspaces/accept/<int:invitation_id>')
def accept_workspace_invite(invitation_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM workspace_invitations WHERE invitation_id = %s AND invited_user_id = %s",
                (invitation_id, session['user_id']))
    invite = cur.fetchone()

    if invite:
        try:
            cur.execute("UPDATE workspace_invitations SET accepted_at = NOW() WHERE invitation_id = %s", (invitation_id,))
            # Only insert if not already a member
            cur.execute("""
                INSERT INTO workspace_members (workspace_id, user_id, is_admin)
                SELECT %s, %s, FALSE
                WHERE NOT EXISTS (
                    SELECT 1 FROM workspace_members
                    WHERE workspace_id = %s AND user_id = %s
                )
            """, (invite['workspace_id'], session['user_id'],
                  invite['workspace_id'], session['user_id']))
            conn.commit()
            flash('You joined the workspace!', 'success')
            return redirect(url_for('workspace', workspace_id=invite['workspace_id']))
        except Exception:
            conn.rollback()
            flash('Error accepting invitation.', 'error')

    cur.close()
    conn.close()
    return redirect(url_for('workspaces'))


# ------------------------------------------------------------------
# Channels
# ------------------------------------------------------------------

@app.route('/workspaces/<int:workspace_id>/channels/new', methods=['GET', 'POST'])
def new_channel(workspace_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
                (workspace_id, session['user_id']))
    if not cur.fetchone():
        flash('You are not a member of this workspace.', 'error')
        return redirect(url_for('workspaces'))

    cur.execute("SELECT * FROM workspaces WHERE workspace_id = %s", (workspace_id,))
    ws = cur.fetchone()

    if request.method == 'POST':
        name         = request.form.get('name', '').strip().lower().replace(' ', '-')
        channel_type = request.form.get('type', 'public')

        if not name:
            flash('Channel name is required.', 'error')
        else:
            try:
                cur.execute("""
                    INSERT INTO channels (workspace_id, name, type, creator_id)
                    VALUES (%s, %s, %s, %s) RETURNING channel_id
                """, (workspace_id, name, channel_type, session['user_id']))
                channel_id = cur.fetchone()['channel_id']
                cur.execute("INSERT INTO channel_members (channel_id, user_id) VALUES (%s, %s)",
                            (channel_id, session['user_id']))
                conn.commit()
                return redirect(url_for('channel', channel_id=channel_id))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                flash('A channel with that name already exists.', 'error')
            except Exception:
                conn.rollback()
                flash('Error creating channel.', 'error')

    cur.close()
    conn.close()
    return render_template('new_channel.html', ws=ws, workspace_id=workspace_id)


@app.route('/channels/<int:channel_id>')
def channel(channel_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM channels WHERE channel_id = %s", (channel_id,))
    ch = cur.fetchone()
    if not ch:
        flash('Channel not found.', 'error')
        return redirect(url_for('workspaces'))

    # Check access
    cur.execute("SELECT * FROM channel_members WHERE channel_id = %s AND user_id = %s",
                (channel_id, session['user_id']))
    membership = cur.fetchone()
    if not membership:
        cur.execute("SELECT * FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
                    (ch['workspace_id'], session['user_id']))
        ws_mem = cur.fetchone()
        if ch['type'] == 'public' and ws_mem:
            # Auto-join public channel
            cur.execute("INSERT INTO channel_members (channel_id, user_id) VALUES (%s, %s)",
                        (channel_id, session['user_id']))
            conn.commit()
        else:
            flash('You do not have access to this channel.', 'error')
            return redirect(url_for('workspace', workspace_id=ch['workspace_id']))

    # Get messages — includes user_id and is_edited for edit link and edited label
    cur.execute("""
        SELECT m.message_id, m.body, m.posted_at, m.user_id, m.is_edited,
               u.username, u.nickname
        FROM messages m
        JOIN users u ON u.user_id = m.user_id
        WHERE m.channel_id = %s
        ORDER BY m.posted_at ASC
    """, (channel_id,))
    messages = cur.fetchall()

    # Get workspace and sidebar channels
    cur.execute("SELECT * FROM workspaces WHERE workspace_id = %s", (ch['workspace_id'],))
    ws = cur.fetchone()

    cur.execute("""
        SELECT c.channel_id, c.name, c.type
        FROM channels c
        WHERE c.workspace_id = %s
          AND (
            c.type = 'public'
            OR EXISTS(SELECT 1 FROM channel_members cm WHERE cm.channel_id = c.channel_id AND cm.user_id = %s)
          )
        ORDER BY c.type, c.name
    """, (ch['workspace_id'], session['user_id']))
    sidebar_channels = cur.fetchall()

    cur.execute("SELECT * FROM workspace_members WHERE workspace_id = %s AND user_id = %s",
                (ch['workspace_id'], session['user_id']))
    ws_membership = cur.fetchone()

    cur.close()
    conn.close()
    return render_template('channel.html', ch=ch, messages=messages, ws=ws,
                           sidebar_channels=sidebar_channels, ws_membership=ws_membership)


@app.route('/channels/<int:channel_id>/post', methods=['POST'])
def post_message(channel_id):
    redir = require_login()
    if redir: return redir

    body = request.form.get('body', '').strip()
    if not body:
        return redirect(url_for('channel', channel_id=channel_id))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM channel_members WHERE channel_id = %s AND user_id = %s",
                (channel_id, session['user_id']))
    if cur.fetchone():
        cur.execute("INSERT INTO messages (channel_id, user_id, body) VALUES (%s, %s, %s)",
                    (channel_id, session['user_id'], body))
        conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('channel', channel_id=channel_id))


@app.route('/channels/<int:channel_id>/invite', methods=['GET', 'POST'])
def invite_to_channel(channel_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM channels WHERE channel_id = %s", (channel_id,))
    ch = cur.fetchone()

    cur.execute("SELECT * FROM channel_members WHERE channel_id = %s AND user_id = %s",
                (channel_id, session['user_id']))
    if not cur.fetchone():
        flash('You are not a member of this channel.', 'error')
        return redirect(url_for('workspace', workspace_id=ch['workspace_id']))

    cur.execute("SELECT * FROM workspaces WHERE workspace_id = %s", (ch['workspace_id'],))
    ws = cur.fetchone()

    if request.method == 'POST':
        invitee_username = request.form.get('username', '').strip()
        cur.execute("SELECT user_id FROM users WHERE username = %s", (invitee_username,))
        invitee = cur.fetchone()

        if not invitee:
            flash('User not found.', 'error')
        else:
            try:
                cur.execute("""
                    INSERT INTO channel_invitations (channel_id, invited_user_id, invited_by)
                    VALUES (%s, %s, %s)
                """, (channel_id, invitee['user_id'], session['user_id']))
                conn.commit()
                flash(f'Invitation sent to {invitee_username}.', 'success')
            except Exception:
                conn.rollback()
                flash('Could not send invitation.', 'error')

    cur.close()
    conn.close()
    return render_template('invite_channel.html', ch=ch, ws=ws)


@app.route('/channels/accept/<int:invitation_id>')
def accept_channel_invite(invitation_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM channel_invitations WHERE invitation_id = %s AND invited_user_id = %s",
                (invitation_id, session['user_id']))
    invite = cur.fetchone()

    if invite:
        try:
            cur.execute("UPDATE channel_invitations SET accepted_at = NOW() WHERE invitation_id = %s", (invitation_id,))
            # Only insert if not already a member
            cur.execute("""
                INSERT INTO channel_members (channel_id, user_id)
                SELECT %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM channel_members
                    WHERE channel_id = %s AND user_id = %s
                )
            """, (invite['channel_id'], session['user_id'],
                  invite['channel_id'], session['user_id']))
            conn.commit()
            flash('You joined the channel!', 'success')
            return redirect(url_for('channel', channel_id=invite['channel_id']))
        except Exception:
            conn.rollback()
            flash('Error accepting invitation.', 'error')

    cur.close()
    conn.close()
    return redirect(url_for('workspaces'))


# ------------------------------------------------------------------
# Edit a message
# ------------------------------------------------------------------

@app.route('/messages/<int:message_id>/edit', methods=['GET', 'POST'])
def edit_message(message_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM messages WHERE message_id = %s", (message_id,))
    msg = cur.fetchone()

    if not msg or int(msg['user_id']) != int(session['user_id']):
        flash('You can only edit your own messages.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('workspaces'))

    if request.method == 'POST':
        new_body = request.form.get('body', '').strip()
        if new_body:
            cur.execute(
                "UPDATE messages SET body = %s, is_edited = TRUE WHERE message_id = %s",
                (new_body, message_id)
            )
            conn.commit()
            flash('Message updated.', 'success')
            cur.close()
            conn.close()
            return redirect(url_for('channel', channel_id=msg['channel_id']))
        else:
            flash('Message cannot be empty.', 'error')

    cur.close()
    conn.close()
    return render_template('edit_message.html', msg=msg)


# ------------------------------------------------------------------
# Bookmarks
# ------------------------------------------------------------------

@app.route('/channels/<int:channel_id>/bookmark')
def toggle_bookmark(channel_id):
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT 1 FROM bookmarks WHERE user_id = %s AND channel_id = %s",
                (session['user_id'], channel_id))
    exists = cur.fetchone()

    if exists:
        cur.execute("DELETE FROM bookmarks WHERE user_id = %s AND channel_id = %s",
                    (session['user_id'], channel_id))
        flash('Bookmark removed.', 'success')
    else:
        cur.execute("INSERT INTO bookmarks (user_id, channel_id) VALUES (%s, %s)",
                    (session['user_id'], channel_id))
        flash('Channel bookmarked.', 'success')

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('channel', channel_id=channel_id))


@app.route('/bookmarks')
def bookmarks():
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT c.channel_id, c.name AS channel_name, c.type,
               w.name AS workspace_name, w.workspace_id
        FROM bookmarks b
        JOIN channels c ON c.channel_id = b.channel_id
        JOIN workspaces w ON w.workspace_id = c.workspace_id
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
    """, (session['user_id'],))
    bookmarked_channels = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('bookmarks.html', bookmarked_channels=bookmarked_channels)


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

@app.route('/search')
def search():
    redir = require_login()
    if redir: return redir

    keyword      = request.args.get('q', '').strip()
    workspace_id = request.args.get('workspace_id', type=int)
    results      = []

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT w.workspace_id, w.name FROM workspaces w
        JOIN workspace_members wm ON wm.workspace_id = w.workspace_id
        WHERE wm.user_id = %s ORDER BY w.name
    """, (session['user_id'],))
    workspaces_list = cur.fetchall()

    if keyword:
        ws_filter = "AND c.workspace_id = %s" if workspace_id else ""
        params = [session['user_id'], session['user_id'], f'%{keyword}%']
        if workspace_id:
            params.append(workspace_id)

        cur.execute(f"""
            SELECT m.body, m.posted_at, u.username, c.name AS channel_name,
                   w.name AS workspace_name, c.channel_id
            FROM messages m
            JOIN users u ON u.user_id = m.user_id
            JOIN channels c ON c.channel_id = m.channel_id
            JOIN workspaces w ON w.workspace_id = c.workspace_id
            JOIN workspace_members wm ON wm.workspace_id = c.workspace_id AND wm.user_id = %s
            JOIN channel_members cm ON cm.channel_id = m.channel_id AND cm.user_id = %s
            WHERE m.body ILIKE %s
            {ws_filter}
            ORDER BY m.posted_at DESC
        """, params)
        results = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('search.html', results=results, keyword=keyword,
                           workspaces=workspaces_list, selected_workspace=workspace_id)


# ------------------------------------------------------------------
# Profile
# ------------------------------------------------------------------

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    redir = require_login()
    if redir: return redir

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
    user = cur.fetchone()

    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        cur.execute("UPDATE users SET nickname = %s WHERE user_id = %s",
                    (nickname, session['user_id']))
        conn.commit()
        session['nickname'] = nickname
        flash('Profile updated.', 'success')

    cur.close()
    conn.close()
    return render_template('profile.html', user=user)


if __name__ == '__main__':
    app.run(debug=True, port=5001)
